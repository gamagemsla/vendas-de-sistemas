"""Worker de segundo plano para processar cadências, despachar outbox, ingerir leads e enriquecer leads."""

from __future__ import annotations

import asyncio
import json
import signal
import sys
import time
import uuid
from typing import Any, NoReturn

import structlog

from vendas.application.commands.enrich_lead import EnrichLeadCommand
from vendas.application.commands.handle_inbound import HandleInboundCommand
from vendas.application.commands.ingest_leads import IngestLeadsCommand
from vendas.application.commands.process_cadence_step import ProcessCadenceStepCommand
from vendas.bootstrap.container import container
from vendas.bootstrap.logging import clear_correlation_id, configure_logging, set_correlation_id
from vendas.bootstrap.settings import settings
from vendas.domain.ports import JobQueue, JobResult

logger = structlog.get_logger()


class Worker:
    """Worker principal que roda o loop de despacho e cadências."""

    def __init__(
        self,
        poll_interval_seconds: int | None = None,
        batch_size: int | None = None,
    ) -> None:
        poll_val = getattr(settings, "WORKER_POLL_INTERVAL_SECONDS", 60)
        self._poll_interval: int = int(
            poll_interval_seconds if poll_interval_seconds is not None else poll_val
        )
        batch_val = getattr(settings, "WORKER_BATCH_SIZE", 10)
        self._batch_size: int = int(batch_size if batch_size is not None else batch_val)
        self._shutdown = False

        # Unique worker ID for this process
        self._worker_id: str = f"worker-{uuid.uuid4().hex[:8]}"

        # Intervalos de ingestão e enriquecimento
        self._ingest_interval: int = int(getattr(settings, "WORKER_INGEST_INTERVAL_SECONDS", 300))
        self._enrich_interval: int = int(getattr(settings, "WORKER_ENRICH_INTERVAL_SECONDS", 60))
        self._ingest_counter: int = 0
        self._enrich_counter: int = 0

        # Lease duration for inbound event claiming (seconds)
        self._inbound_lease_seconds: int = int(
            getattr(settings, "WORKER_INBOUND_LEASE_SECONDS", 300)
        )

        # Max attempts before permanent failure
        self._inbound_max_attempts: int = int(getattr(settings, "WORKER_INBOUND_MAX_ATTEMPTS", 5))

        # Dependências via container (bootstrap) — respeita arquitetura hexagonal
        self._dispatcher: Any = container.get_outbox_dispatcher()
        self._cadence_processor: ProcessCadenceStepCommand = (
            container.get_process_cadence_step_command()
        )
        self._ingest_cmd: IngestLeadsCommand = container.get_ingest_leads_command()
        self._enrich_cmd: EnrichLeadCommand = container.get_enrich_lead_command()
        self._inbound_cmd: HandleInboundCommand = container.get_handle_inbound_command()
        self._job_queue: JobQueue = container.job_queue

        # Signal handlers para shutdown gracioso
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum: int, frame: object) -> None:
        logger.info("sinal_recebido_iniciando_shutdown", signal=signum)
        self._shutdown = True

    def _check_kill_switch(self) -> bool:
        """Verificação MANDATÓRIA do KILL_SWITCH antes de qualquer trabalho."""
        if settings.KILL_SWITCH:
            logger.warning("kill_switch_ativo_parando_worker", kill_switch=True)
            return True
        return False

    def _run_dispatch_cycle(self) -> int:
        """Executa um ciclo de despacho da outbox."""
        cid = set_correlation_id(f"dispatch-{int(time.time() * 1000)}")
        try:
            logger.info("iniciando_ciclo_dispatch_outbox", correlation_id=cid)
            processed = self._dispatcher.dispatch_batch(batch_size=self._batch_size)
            logger.info("ciclo_dispatch_concluido", processed=processed, correlation_id=cid)
            return int(processed)
        except Exception as exc:
            logger.exception("erro_no_ciclo_dispatch", error=str(exc), correlation_id=cid)
            return 0
        finally:
            clear_correlation_id()

    def _run_cadence_cycle(self) -> int:
        """Executa um ciclo de processamento de cadências."""
        if settings.CADENCE_GLOBAL_PAUSE:
            logger.warning("cadencia_global_pausada", cadence_global_pause=True)
            return 0
        cid = set_correlation_id(f"cadence-{int(time.time() * 1000)}")
        try:
            logger.info("iniciando_ciclo_processamento_cadencia", correlation_id=cid)
            processed = self._cadence_processor.execute(batch_size=self._batch_size)
            logger.info("ciclo_cadencia_concluido", processed=processed, correlation_id=cid)
            return int(processed)
        except Exception as exc:
            logger.exception("erro_no_ciclo_cadencia", error=str(exc), correlation_id=cid)
            return 0
        finally:
            clear_correlation_id()

    def _run_ingest_cycle(self) -> int:
        """Executa um ciclo de ingestão de leads."""
        if self._check_kill_switch():
            return 0
        cid = set_correlation_id(f"ingest-{int(time.time() * 1000)}")
        try:
            logger.info("iniciando_ciclo_ingestao", correlation_id=cid)
            search_query = json.loads(settings.INGEST_SEARCH_QUERY)
            ingested = self._ingest_cmd.execute(search_query)
            logger.info("ciclo_ingestao_concluido", ingested=ingested, correlation_id=cid)
            return int(ingested)
        except Exception as exc:
            logger.exception("erro_no_ciclo_ingestao", error=str(exc), correlation_id=cid)
            return 0
        finally:
            clear_correlation_id()

    async def _run_enrich_cycle(self) -> int:
        """Executa um ciclo de enriquecimento de leads processando jobs da fila."""
        if self._check_kill_switch():
            return 0
        processed = 0
        cid = set_correlation_id(f"enrich-{int(time.time() * 1000)}")
        try:
            logger.info("iniciando_ciclo_enriquecimento", correlation_id=cid)
            # Use the JobQueue port properly with worker_id, max_jobs, queue_names
            jobs = await self._job_queue.dequeue(
                worker_id=self._worker_id,
                max_jobs=self._batch_size,
                queue_names=["enrich_lead"],
            )
            for job in jobs:
                if job.name != "enrich_lead":
                    # Requeue jobs of other types instead of discarding
                    logger.warning(
                        "job_tipo_inesperado_requeue", job_name=job.name, job_id=str(job.id)
                    )
                    await self._job_queue.requeue(job.id)
                    continue
                lead_id = job.payload.get("lead_id")
                if lead_id:
                    try:
                        self._enrich_cmd.execute(lead_id)
                        result = JobResult(success=True, result={"lead_id": lead_id})
                        await self._job_queue.complete(job.id, result)
                        processed += 1
                    except Exception as exc:
                        logger.exception(
                            "erro_processando_job_enriquecimento",
                            job_id=str(job.id),
                            error=str(exc),
                        )
                        # Check if should retry
                        if job.retry_count < job.max_retries:
                            result = JobResult(success=False, error=str(exc), should_retry=True)
                            await self._job_queue.complete(job.id, result)
                            # Requeue with backoff
                            from vendas.domain.policies.retry_policy import compute_next_retry_at

                            clock = container.clock
                            delay = int(
                                (
                                    compute_next_retry_at(clock.now(), job.retry_count + 1)
                                    - clock.now()
                                ).total_seconds()
                            )
                            await self._job_queue.requeue(job.id, delay_seconds=max(1, delay))
                        else:
                            result = JobResult(success=False, error=str(exc), should_retry=False)
                            await self._job_queue.complete(job.id, result)
                else:
                    logger.warning("job_enriquecimento_payload_invalido", job_id=str(job.id))
                    result = JobResult(
                        success=False, error="Invalid payload: missing lead_id", should_retry=False
                    )
                    await self._job_queue.complete(job.id, result)
            logger.info("ciclo_enriquecimento_concluido", processed=processed, correlation_id=cid)
            return processed
        except Exception as exc:
            logger.exception("erro_no_ciclo_enriquecimento", error=str(exc), correlation_id=cid)
            return 0
        finally:
            clear_correlation_id()

    def _run_inbound_cycle(self) -> int:
        """Executa um ciclo de processamento de mensagens inbound (handle_inbound).

        Usa claim_batch do repositório de inbound_events (SELECT FOR UPDATE SKIP LOCKED)
        para reivindicar eventos não processados, processa cada um isoladamente
        e marca o resultado. A falha de um evento não derruba os demais.
        """
        if self._check_kill_switch():
            return 0
        processed = 0
        cid = set_correlation_id(f"inbound-{int(time.time() * 1000)}")
        try:
            logger.info("iniciando_ciclo_inbound", correlation_id=cid)

            # Get UoW to access inbound_events repository
            from vendas.bootstrap.container import container

            uow_factory = container.get_uow_factory()

            with uow_factory() as uow:
                now = uow._clock.now()
                # Claim batch of unprocessed events
                assert uow.inbound_events is not None
                claimed_events = uow.inbound_events.claim_batch(
                    lease_seconds=self._inbound_lease_seconds,
                    batch_size=self._batch_size,
                    now=now,
                )

            # Process each claimed event OUTSIDE the transaction (no network calls in transaction)
            for event in claimed_events:
                if self._check_kill_switch():
                    break

                sender_phone = event.payload.get("remoteJid") or event.payload.get("data", {}).get(
                    "key", {}
                ).get("remoteJid")
                message_text = (
                    event.payload.get("data", {}).get("message", {}).get("conversation")
                    or event.payload.get("data", {})
                    .get("message", {})
                    .get("extendedTextMessage", {})
                    .get("text")
                    or ""
                )
                provider_message_id = event.provider_event_id

                if not sender_phone or not message_text or not provider_message_id:
                    logger.warning("evento_inbound_payload_invalido", event_id=str(event.id))
                    # Mark as failed permanently
                    with uow_factory() as uow:
                        assert uow.inbound_events is not None
                        ev = uow.inbound_events.get(event.id)
                        if ev:
                            ev.mark_as_failed(
                                "Invalid payload: missing required fields", at=uow._clock.now()
                            )
                            uow.inbound_events.save(ev)
                            uow.commit()
                    continue

                try:
                    # Process the inbound message
                    self._inbound_cmd.execute(
                        sender_phone=sender_phone,
                        message_text=message_text,
                        provider_message_id=provider_message_id,
                    )
                    # Mark as processed successfully
                    with uow_factory() as uow:
                        assert uow.inbound_events is not None
                        ev = uow.inbound_events.get(event.id)
                        if ev:
                            ev.mark_as_processed(at=uow._clock.now())
                            uow.inbound_events.save(ev)
                            uow.commit()
                    processed += 1
                except Exception as exc:
                    logger.exception(
                        "erro_processando_evento_inbound", event_id=str(event.id), error=str(exc)
                    )
                    # Mark as failed with retry logic
                    with uow_factory() as uow:
                        assert uow.inbound_events is not None
                        ev = uow.inbound_events.get(event.id)
                        if ev:
                            if ev.attempts >= self._inbound_max_attempts:
                                # Max attempts reached - permanent failure
                                ev.mark_as_failed(
                                    f"Max attempts reached: {exc}", at=uow._clock.now()
                                )
                                uow.inbound_events.save(ev)
                                uow.commit()
                                logger.error(
                                    "evento_inbound_falha_definitiva",
                                    event_id=str(event.id),
                                    attempts=ev.attempts,
                                )
                            else:
                                # Will be retried - release lock, keep attempts incremented
                                ev.release(at=uow._clock.now())
                                uow.inbound_events.save(ev)
                                uow.commit()
                                logger.warning(
                                    "evento_inbound_falha_temporaria",
                                    event_id=str(event.id),
                                    attempts=ev.attempts,
                                )

            logger.info("ciclo_inbound_concluido", processed=processed, correlation_id=cid)
            return processed
        except Exception as exc:
            logger.exception("erro_no_ciclo_inbound", error=str(exc), correlation_id=cid)
            return 0
        finally:
            clear_correlation_id()

    async def run(self) -> NoReturn:
        """Loop principal do worker — roda até shutdown ou KILL_SWITCH."""
        logger.info(
            "worker_iniciado",
            poll_interval_seconds=self._poll_interval,
            batch_size=self._batch_size,
            ingest_interval_seconds=self._ingest_interval,
            enrich_interval_seconds=self._enrich_interval,
            dry_run=settings.DRY_RUN,
            automation_enabled=settings.AUTOMATION_ENABLED,
        )

        while not self._shutdown:
            # 1. KILL_SWITCH check OBRIGATÓRIO no topo do loop
            if self._check_kill_switch():
                break

            # 2. Ciclo de despacho da outbox
            self._run_dispatch_cycle()

            # 3. Ciclo de processamento de inbound (handle_inbound)
            self._run_inbound_cycle()

            # 4. KILL_SWITCH check entre ciclos
            if self._check_kill_switch():
                break

            # 5. Ciclo de processamento de cadências
            self._run_cadence_cycle()

            # 5. KILL_SWITCH check antes de ingestão
            if self._check_kill_switch():
                break

            # 6. Ciclo de ingestão (controlado por contador)
            self._ingest_counter += self._poll_interval
            if self._ingest_counter >= self._ingest_interval:
                self._run_ingest_cycle()
                self._ingest_counter = 0

            # 7. KILL_SWITCH check antes de enriquecimento
            if self._check_kill_switch():
                break

            # 8. Ciclo de enriquecimento (controlado por contador)
            self._enrich_counter += self._poll_interval
            if self._enrich_counter >= self._enrich_interval:
                await self._run_enrich_cycle()
                self._enrich_counter = 0

            # 9. Sleep configurável (respeita shutdown durante o sleep)
            for _ in range(self._poll_interval):
                if self._shutdown or settings.KILL_SWITCH:
                    break
                await asyncio.sleep(1)

        logger.info(
            "worker_finalizado", shutdown_requested=self._shutdown, kill_switch=settings.KILL_SWITCH
        )
        sys.exit(0)


def main() -> NoReturn:
    """Ponto de entrada CLI: `python -m vendas.interfaces.worker`."""
    import asyncio

    configure_logging()

    worker = Worker()
    asyncio.run(worker.run())


if __name__ == "__main__":
    main()

"""Worker de segundo plano para processar cadências, despachar outbox, ingerir leads e enriquecer leads."""

from __future__ import annotations

import json
import signal
import sys
import time
from typing import Any, NoReturn

import structlog

from vendas.application.commands.enrich_lead import EnrichLeadCommand
from vendas.application.commands.ingest_leads import IngestLeadsCommand
from vendas.application.commands.process_cadence_step import ProcessCadenceStepCommand
from vendas.bootstrap.container import container
from vendas.bootstrap.logging import clear_correlation_id, configure_logging, set_correlation_id
from vendas.bootstrap.settings import settings

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

        # Intervalos de ingestão e enriquecimento
        self._ingest_interval: int = int(getattr(settings, "WORKER_INGEST_INTERVAL_SECONDS", 300))
        self._enrich_interval: int = int(getattr(settings, "WORKER_ENRICH_INTERVAL_SECONDS", 60))
        self._ingest_counter: int = 0
        self._enrich_counter: int = 0

        # Dependências via container (bootstrap) — respeita arquitetura hexagonal
        self._dispatcher: Any = container.get_outbox_dispatcher()
        self._cadence_processor: ProcessCadenceStepCommand = (
            container.get_process_cadence_step_command()
        )
        self._ingest_cmd: IngestLeadsCommand = container.get_ingest_leads_command()
        self._enrich_cmd: EnrichLeadCommand = container.get_enrich_lead_command()
        self._job_queue: Any = container.job_queue

        # Signal handlers para shutdown gracioso
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

    def _run_enrich_cycle(self) -> int:
        """Executa um ciclo de enriquecimento de leads processando jobs da fila."""
        if self._check_kill_switch():
            return 0
        processed = 0
        cid = set_correlation_id(f"enrich-{int(time.time() * 1000)}")
        try:
            logger.info("iniciando_ciclo_enriquecimento", correlation_id=cid)
            for _ in range(self._batch_size):
                job = self._job_queue.dequeue()
                if not job:
                    break
                if job.name != "enrich_lead":
                    # Re-enfileira jobs desconhecidos ou ignora
                    continue
                lead_id = job.payload.get("lead_id")
                if lead_id:
                    self._enrich_cmd.execute(lead_id)
                    processed += 1
            logger.info("ciclo_enriquecimento_concluido", processed=processed, correlation_id=cid)
            return processed
        except Exception as exc:
            logger.exception("erro_no_ciclo_enriquecimento", error=str(exc), correlation_id=cid)
            return 0
        finally:
            clear_correlation_id()

    def run(self) -> NoReturn:
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

            # 3. KILL_SWITCH check entre ciclos
            if self._check_kill_switch():
                break

            # 4. Ciclo de processamento de cadências
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
                self._run_enrich_cycle()
                self._enrich_counter = 0

            # 9. Sleep configurável (respeita shutdown durante o sleep)
            for _ in range(self._poll_interval):
                if self._shutdown or settings.KILL_SWITCH:
                    break
                time.sleep(1)

        logger.info(
            "worker_finalizado", shutdown_requested=self._shutdown, kill_switch=settings.KILL_SWITCH
        )
        sys.exit(0)


def main() -> NoReturn:
    """Ponto de entrada CLI: `python -m vendas.interfaces.worker`."""
    configure_logging()

    worker = Worker()
    worker.run()


if __name__ == "__main__":
    main()

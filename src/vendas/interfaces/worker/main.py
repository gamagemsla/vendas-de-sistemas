"""Worker de segundo plano para processar cadências e despachar outbox."""

import signal
import sys
import time
from typing import NoReturn

import structlog

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
        self._poll_interval = poll_interval_seconds or getattr(settings, "WORKER_POLL_INTERVAL_SECONDS", 60)
        self._batch_size = batch_size or getattr(settings, "WORKER_BATCH_SIZE", 10)
        self._shutdown = False

        # Dependências via container (bootstrap) — respeita arquitetura hexagonal
        self._dispatcher = container.get_outbox_dispatcher()
        self._cadence_processor = container.get_process_cadence_step_command()

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
            return processed
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
            return processed
        except Exception as exc:
            logger.exception("erro_no_ciclo_cadencia", error=str(exc), correlation_id=cid)
            return 0
        finally:
            clear_correlation_id()

    def run(self) -> NoReturn:
        """Loop principal do worker — roda até shutdown ou KILL_SWITCH."""
        logger.info(
            "worker_iniciado",
            poll_interval_seconds=self._poll_interval,
            batch_size=self._batch_size,
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

            # 5. Sleep configurável (respeita shutdown durante o sleep)
            for _ in range(self._poll_interval):
                if self._shutdown or settings.KILL_SWITCH:
                    break
                time.sleep(1)

        logger.info("worker_finalizado", shutdown_requested=self._shutdown, kill_switch=settings.KILL_SWITCH)
        sys.exit(0)


def main() -> NoReturn:
    """Ponto de entrada CLI: `python -m vendas.interfaces.worker`."""
    configure_logging()

    worker = Worker()
    worker.run()


if __name__ == "__main__":
    main()
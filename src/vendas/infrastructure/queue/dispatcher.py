import structlog

from vendas.bootstrap.logging import clear_correlation_id, set_correlation_id
from vendas.bootstrap.settings import settings
from vendas.domain.entities.outbox_payloads import (
    InvalidOutboxPayloadError,
    validate_outbox_payload,
)
from vendas.domain.ports.message_channel import MessageChannel
from vendas.domain.ports.uow import UnitOfWork

logger = structlog.get_logger()


class OutboxDispatcher:
    """Processa a tabela outbox de forma transacional, garantindo idempotência e DRY_RUN."""

    def __init__(self, uow: UnitOfWork, channel: MessageChannel) -> None:
        self._uow = uow
        self._channel = channel

    def dispatch_batch(self, batch_size: int = 10) -> int:
        # Interrupção imediata se KILL_SWITCH ativo — antes de qualquer transação
        if settings.KILL_SWITCH:
            logger.warning("worker_parado_kill_switch", kill_switch=True)
            return 0

        processed_count = 0

        with self._uow as uow:
            # Busca itens pendentes usando o SKIP LOCKED implementado na F1-08
            pending_items = uow.outbox.claim_pending(batch_size=batch_size)
            if not pending_items:
                return 0

            for item in pending_items:
                # Define correlation_id para este item (payload ou id do item)
                payload = item.payload
                cid = None
                if isinstance(payload, dict):
                    cid = payload.get("correlation_id")
                set_correlation_id(cid or str(item.id))

                try:
                    logger.info(
                        "processando_outbox_item",
                        outbox_id=item.id,
                        event_type=item.event_type,
                    )

                    # Valida payload antes de qualquer envio (DRY_RUN ou real)
                    validated_payload = validate_outbox_payload(item.event_type, item.payload)

                    # REGRA DE OURO: DRY_RUN=true impede qualquer envio real
                    if settings.DRY_RUN:
                        logger.info(
                            "dry_run_ativo_mensagem_simulada",
                            outbox_id=item.id,
                            event_type=item.event_type,
                            payload=validated_payload,
                            idempotency_key=item.idempotency_key,
                        )
                        uow.outbox.mark_as_sent(str(item.id))
                    else:
                        if not settings.AUTOMATION_ENABLED:
                            raise RuntimeError(
                                "Automação desativada via configuração (AUTOMATION_ENABLED=false)"
                            )

                        # Envio real através do Port do Canal de Mensagem
                        self._channel.send(validated_payload)
                        uow.outbox.mark_as_sent(str(item.id))

                    processed_count += 1

                except (
                    OSError,
                    RuntimeError,
                    TimeoutError,
                    ValueError,
                    InvalidOutboxPayloadError,
                ) as exc:
                    logger.error("erro_envio_outbox", outbox_id=item.id, error=str(exc))
                    uow.outbox.mark_as_failed(str(item.id), error_message=str(exc))
                finally:
                    clear_correlation_id()

            uow.commit()

        return processed_count

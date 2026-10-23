from datetime import UTC, datetime
from unittest.mock import MagicMock

from tests.fakes.fakes import InMemoryConversationLock
from vendas.application.commands.handle_inbound import HandleInboundCommand
from vendas.application.commands.schedule_meeting import ScheduleMeetingCommand
from vendas.infrastructure.channels.telegram_notifier import TelegramNotifier


def test_opt_out_intercepted_before_ai():
    """Garante que o opt-out é detectado e bloqueia o lead imediatamente sem acionar o agente de IA."""
    uow = MagicMock()
    # Mágica do mock: faz o context manager (with) retornar o próprio uow configurado
    uow.__enter__.return_value = uow

    agent = MagicMock()
    clock = MagicMock()

    inbound_mock = MagicMock()
    inbound_mock.exists.return_value = False
    uow.inbound_events = inbound_mock

    lead_mock = MagicMock()
    lead_mock.status = "NEW"
    uow.leads.find_by_dedupe_key.return_value = lead_mock

    command = HandleInboundCommand(
        uow=uow,
        agent=agent,
        knowledge_base=MagicMock(),
        clock=clock,
        conversation_lock_factory=lambda _session: InMemoryConversationLock(),
    )

    command.execute(
        sender_phone="+5511999999999",
        message_text="SAIR",
        provider_message_id="msg-123",
    )

    lead_mock.mark_as_opted_out.assert_called_once()
    agent.decide.assert_not_called()
    uow.commit.assert_called()


def test_inbound_webhook_deduplication():
    """Garante que eventos de webhook duplicados (mesmo provider_message_id) são ignorados."""
    uow = MagicMock()
    agent = MagicMock()
    clock = MagicMock()

    uow.inbound_events.exists.return_value = True

    command = HandleInboundCommand(
        uow=uow,
        agent=agent,
        knowledge_base=MagicMock(),
        clock=clock,
        conversation_lock_factory=lambda _session: InMemoryConversationLock(),
    )
    command.execute(
        sender_phone="+5511999999999",
        message_text="Olá",
        provider_message_id="msg-duplicada",
    )

    uow.leads.find_by_dedupe_key.assert_not_called()
    agent.decide.assert_not_called()


def test_schedule_meeting_double_booking_prevention():
    """Garante que dois agendamentos disputando o mesmo horário impedem o conflito."""
    uow = MagicMock()
    notifier = MagicMock()
    clock = MagicMock()

    uow.bookings.exists_at.return_value = True

    command = ScheduleMeetingCommand(uow=uow, notifier=notifier, clock=clock)
    slot = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)

    success = command.execute(lead_id="lead-1", slot_time=slot)

    assert success is False
    notifier.send_alert.assert_not_called()


def test_telegram_notifier_resilience_when_down():
    """Garante que se a API do Telegram falhar, o fluxo não quebra (falha silenciosa segura)."""
    client_mock = MagicMock()
    client_mock.post.side_effect = Exception("Telegram connection timeout")

    notifier = TelegramNotifier(bot_token="fake-token", chat_id="123", client=client_mock)

    success = notifier.send_alert("Teste de alerta com Telegram fora do ar")

    assert success is False

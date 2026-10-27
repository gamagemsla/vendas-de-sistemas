"""Testes de blindagem do DRY_RUN no OutboxDispatcher."""

from __future__ import annotations

from typing import Self
from unittest.mock import MagicMock, patch

import pytest

from vendas.bootstrap.settings import Settings
from vendas.domain.entities.outbox_payloads import validate_outbox_payload
from vendas.domain.ports.message_channel import MessageChannel
from vendas.infrastructure.queue.dispatcher import OutboxDispatcher


class FakeOutboxItem:
    def __init__(self, id: int, event_type: str, payload: dict, idempotency_key: str) -> None:
        self.id = id
        self.event_type = event_type
        self.payload = payload
        self.idempotency_key = idempotency_key


class FakeOutboxRepo:
    def __init__(self, items: list[FakeOutboxItem]) -> None:
        self._items = items
        self.marked_sent: list[int] = []
        self.marked_failed: list[tuple[int, str, bool]] = []

    def claim_pending(self, batch_size: int) -> list[FakeOutboxItem]:
        return self._items[:batch_size]

    def mark_sent(self, outbox_id: str) -> None:
        self.marked_sent.append(int(outbox_id))

    def mark_failed(self, outbox_id: str, error_message: str, will_retry: bool) -> None:
        self.marked_failed.append((int(outbox_id), error_message, will_retry))


class FakeUow:
    def __init__(self, outbox_repo: FakeOutboxRepo) -> None:
        self.outbox = outbox_repo
        self.committed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.committed = True

    def commit(self) -> None:
        self.committed = True


@pytest.fixture
def sample_item() -> FakeOutboxItem:
    return FakeOutboxItem(
        id=1,
        event_type="SEND_AI_RESPONSE",
        payload={"phone": "+5511999999999", "content": "Olá"},
        idempotency_key="idem-123",
    )


@pytest.fixture
def validated_payload(sample_item: FakeOutboxItem) -> dict:
    return validate_outbox_payload(sample_item.event_type, sample_item.payload)


def test_dry_run_true_simulates_and_marks_sent(
    sample_item: FakeOutboxItem, validated_payload: dict
) -> None:
    outbox_repo = FakeOutboxRepo([sample_item])
    uow = FakeUow(outbox_repo)
    channel = MagicMock(spec=MessageChannel)

    with patch(
        "vendas.infrastructure.queue.dispatcher.settings",
        Settings(DRY_RUN=True, AUTOMATION_ENABLED=False, KILL_SWITCH=False),
    ):
        dispatcher = OutboxDispatcher(uow, channel)
        processed = dispatcher.dispatch_batch(batch_size=10)

    assert processed == 1
    assert outbox_repo.marked_sent == [1]
    assert outbox_repo.marked_failed == []
    channel.send.assert_not_called()
    assert uow.committed is True


def test_dry_run_false_automation_disabled_marks_failed(
    sample_item: FakeOutboxItem, validated_payload: dict
) -> None:
    outbox_repo = FakeOutboxRepo([sample_item])
    uow = FakeUow(outbox_repo)
    channel = MagicMock(spec=MessageChannel)

    with patch(
        "vendas.infrastructure.queue.dispatcher.settings",
        Settings(DRY_RUN=False, AUTOMATION_ENABLED=False, KILL_SWITCH=False),
    ):
        dispatcher = OutboxDispatcher(uow, channel)
        processed = dispatcher.dispatch_batch(batch_size=10)

    assert processed == 0
    assert outbox_repo.marked_sent == []
    assert outbox_repo.marked_failed == [
        (1, "Automação desativada via configuração (AUTOMATION_ENABLED=false)", True)
    ]
    channel.send.assert_not_called()
    assert uow.committed is True


def test_dry_run_false_automation_enabled_sends_and_marks_sent(
    sample_item: FakeOutboxItem, validated_payload: dict
) -> None:
    outbox_repo = FakeOutboxRepo([sample_item])
    uow = FakeUow(outbox_repo)
    channel = MagicMock(spec=MessageChannel)
    channel.send.return_value = {"message_id": "msg-123"}

    with patch(
        "vendas.infrastructure.queue.dispatcher.settings",
        Settings(DRY_RUN=False, AUTOMATION_ENABLED=True, KILL_SWITCH=False),
    ):
        dispatcher = OutboxDispatcher(uow, channel)
        processed = dispatcher.dispatch_batch(batch_size=10)

    assert processed == 1
    assert outbox_repo.marked_sent == [1]
    assert outbox_repo.marked_failed == []
    channel.send.assert_called_once_with(validated_payload)
    assert uow.committed is True


def test_log_masking_recursive_on_dry_run(
    sample_item: FakeOutboxItem, validated_payload: dict
) -> None:
    """Cenário 4: LGPD - log de DRY_RUN mascara telefone dentro de payload aninhado."""
    from vendas.bootstrap.logging import mask_sensitive_data

    event_dict = {
        "event": "dry_run_ativo_mensagem_simulada",
        "payload": {"phone": "+5511999999999", "content": "Olá"},
        "outbox_id": 1,
        "event_type": "SEND_AI_RESPONSE",
        "idempotency_key": "idem-123",
    }
    masked = mask_sensitive_data(None, "info", event_dict)
    assert masked["payload"]["phone"] == "+5511****9999"
    assert masked["payload"]["content"] == "Olá"
    assert masked["outbox_id"] == 1
    assert masked["event_type"] == "SEND_AI_RESPONSE"

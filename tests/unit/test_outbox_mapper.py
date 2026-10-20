"""Testes para OutboxMapper (round-trip e validações)."""

from datetime import UTC, datetime
from uuid import uuid4

from vendas.domain.entities.outbox_message import OutboxMessage, OutboxStatus
from vendas.infrastructure.persistence.mappers import OutboxMapper


def test_outbox_mapper_round_trip():
    """Verifica conversão Domain -> ORM -> Domain preserva todos os campos."""
    # Arrange: cria entidade com valores não-default
    entity = OutboxMessage(
        id=uuid4(),
        event_type="lead_created",
        payload={"lead_id": "123", "name": "Test"},
        idempotency_key="idem-001",
        channel="whatsapp",
        destination="+5511999999999",
        template_name="welcome_template",
        template_params={"name": "Test"},
        attempts=2,
        max_attempts=5,
        status=OutboxStatus.PROCESSING,
        last_error=None,
        scheduled_at=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        created_at=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
        processed_at=datetime(2024, 1, 1, 12, 5, tzinfo=UTC),
        provider_message_id="msg-abc",
    )

    # Act: to_orm then to_domain
    model = OutboxMapper.to_orm(entity)
    assert model is not None
    round_trip = OutboxMapper.to_domain(model)

    # Assert: todos os campos iguais
    assert round_trip.id == entity.id
    assert round_trip.event_type == entity.event_type
    assert round_trip.payload == entity.payload
    assert round_trip.idempotency_key == entity.idempotency_key
    assert round_trip.channel == entity.channel
    assert round_trip.destination == entity.destination
    assert round_trip.template_name == entity.template_name
    assert round_trip.template_params == entity.template_params
    assert round_trip.attempts == entity.attempts
    assert round_trip.max_attempts == entity.max_attempts
    assert round_trip.status == entity.status
    assert round_trip.last_error == entity.last_error
    assert round_trip.scheduled_at == entity.scheduled_at
    assert round_trip.created_at == entity.created_at
    assert round_trip.processed_at == entity.processed_at
    assert round_trip.provider_message_id == entity.provider_message_id


def test_outbox_mapper_none_preserved():
    """Campos None devem permanecer None após round-trip."""
    entity = OutboxMessage(
        id=uuid4(),
        event_type="event",
        payload={},
        idempotency_key="k1",
        channel=None,
        destination=None,
        template_name=None,
        template_params=None,
        attempts=0,
        max_attempts=3,
        status=OutboxStatus.PENDING,
        last_error=None,
        scheduled_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        processed_at=None,
        provider_message_id=None,
    )
    model = OutboxMapper.to_orm(entity)
    round_trip = OutboxMapper.to_domain(model)
    assert round_trip.channel is None
    assert round_trip.destination is None
    assert round_trip.template_name is None
    assert round_trip.template_params is None
    assert round_trip.last_error is None
    assert round_trip.processed_at is None
    assert round_trip.provider_message_id is None


def test_outbox_message_create_requires_idempotency_key():
    """OutboxMessage.create deve exigir idempotency_key (TypeError se omitido)."""
    try:
        OutboxMessage.create(
            event_type="test",
            payload={},
            # idempotency_key omitted
            channel="whatsapp",
        )
    except TypeError:
        return
    raise AssertionError("Expected TypeError when idempotency_key missing")

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from vendas.bootstrap.settings import settings
from vendas.infrastructure.persistence.base import Base
from vendas.infrastructure.persistence.orm_models import OutboxModel, OutboxStatus
from vendas.infrastructure.persistence.repositories import SQLAlchemyOutboxRepository


def _make_session() -> Session:
    db_url = settings.DATABASE_URL  # Já aponta para vendas_db_test via conftest.py
    engine = create_engine(db_url, pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return SessionLocal()


def test_outbox_canonical_repository() -> None:
    session = _make_session()
    repo = SQLAlchemyOutboxRepository(session)
    try:
        # a) add via repo using a known event_type with valid payload
        event_type = "SEND_AI_RESPONSE"
        payload = {"phone": "+5511999999999", "content": "Test message"}
        idempotency_key = f"idemp-{uuid4()}"

        repo.add_message(
            event_type=event_type,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        session.flush()

        # read via repo get
        model = session.query(OutboxModel).filter_by(idempotency_key=idempotency_key).one()
        persisted = repo.get(str(model.id))
        assert persisted is not None
        assert persisted.event_type == event_type
        assert persisted.payload == payload
        assert persisted.idempotency_key == idempotency_key
        # status should be pending (lowercase) according to persistence repo
        assert persisted.status.value == "pending"

        # get_pending should also return it
        pending_list = repo.get_pending(limit=10)
        assert any(m.idempotency_key == idempotency_key for m in pending_list)

        # b) claim_pending via repo
        claimed = repo.claim_pending(batch_size=10)
        assert len(claimed) == 1
        claimed_item = claimed[0]
        assert claimed_item.idempotency_key == idempotency_key

        # mark_sent via repo
        repo.mark_sent(str(claimed_item.id))
        session.flush()
        # read via repo
        sent_msg = repo.get(str(claimed_item.id))
        assert sent_msg is not None
        # persistence expects status "sent" lowercase
        assert sent_msg.status.value == "sent"

        # mark_failed via repo (will_retry=False -> failed)
        idempotency_key2 = f"idemp-{uuid4()}"
        repo.add_message(
            event_type="SEND_AI_RESPONSE",
            payload={"phone": "+5511888888888", "content": "Fail test"},
            idempotency_key=idempotency_key2,
        )
        session.flush()
        model2 = session.query(OutboxModel).filter_by(idempotency_key=idempotency_key2).one()
        repo.mark_failed(str(model2.id), error="boom", will_retry=False)
        session.flush()
        failed_msg = repo.get(str(model2.id))
        assert failed_msg is not None
        # should be failed (lowercase)
        assert failed_msg.status.value == "failed"

        # c) duplicate idempotency_key should raise IntegrityError
        try:
            repo.add_message(
                event_type="SEND_AI_RESPONSE",
                payload={"phone": "+5511777777777", "content": "Dup test"},
                idempotency_key=idempotency_key,
            )
            session.flush()
            session.commit()
        except IntegrityError:
            session.rollback()
            # expected
        else:
            assert False, "Expected IntegrityError on duplicate idempotency_key"
    finally:
        session.close()


def test_claim_pending_respects_scheduled_at() -> None:
    session = _make_session()
    repo = SQLAlchemyOutboxRepository(session)
    try:
        now = datetime.now(UTC)

        # 1) future scheduled_at -> should NOT be claimed
        future_msg = OutboxModel(
            event_type="SEND_AI_RESPONSE",
            payload={"phone": "+5511999999999", "content": "Future"},
            idempotency_key=f"idemp-future-{uuid4()}",
            status=OutboxStatus.PENDING,
            scheduled_at=now + timedelta(hours=2),
        )
        session.add(future_msg)

        # 2) past scheduled_at -> SHOULD be claimed
        past_msg = OutboxModel(
            event_type="SEND_AI_RESPONSE",
            payload={"phone": "+5511888888888", "content": "Past"},
            idempotency_key=f"idemp-past-{uuid4()}",
            status=OutboxStatus.PENDING,
            scheduled_at=now - timedelta(hours=1),
        )
        session.add(past_msg)

        # 3) scheduled_at None -> SHOULD be claimed
        none_msg = OutboxModel(
            event_type="SEND_AI_RESPONSE",
            payload={"phone": "+5511777777777", "content": "None"},
            idempotency_key=f"idemp-none-{uuid4()}",
            status=OutboxStatus.PENDING,
            scheduled_at=None,
        )
        session.add(none_msg)

        session.flush()

        claimed = repo.claim_pending(batch_size=10)
        claimed_ids = {m.id for m in claimed}

        assert future_msg.id not in claimed_ids, "Future scheduled message should not be claimed"
        assert past_msg.id in claimed_ids, "Past scheduled message should be claimed"
        assert none_msg.id in claimed_ids, "Message with scheduled_at=None should be claimed"
    finally:
        session.close()

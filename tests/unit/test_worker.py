"""Testes unitários para o worker de segundo plano."""

from __future__ import annotations

import time
from collections.abc import Sequence
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from types import TracebackType
from typing import Any
from uuid import UUID

import pytest

from vendas.bootstrap.settings import settings
from vendas.domain.entities.inbound_event import InboundEvent
from vendas.domain.ports import Clock, Job, JobResult, UnitOfWork
from vendas.interfaces.worker.main import Worker


class FakeClock(Clock):
    """Fake Clock for testing."""

    def __init__(self) -> None:
        self._now = datetime.now(UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        from datetime import timedelta

        self._now += timedelta(seconds=seconds)


class FakeIngestCommand:
    def __init__(self) -> None:
        self.call_count = 0

    def execute(self, search_query: dict) -> int:
        self.call_count += 1
        return 2  # simula 2 leads ingeridos


class FakeEnrichCommand:
    def __init__(self) -> None:
        self.call_count = 0

    def execute(self, lead_id: str) -> None:
        self.call_count += 1


class FakeJobQueue:
    def __init__(self) -> None:
        self._jobs: list[Job] = []
        self.completed_jobs: list[tuple[UUID, JobResult]] = []
        self.requeued_jobs: list[tuple[UUID, int | None]] = []

    async def enqueue(self, job: Job) -> None:
        self._jobs.append(job)

    async def dequeue(
        self,
        worker_id: str,
        max_jobs: int,
        queue_names: list[str] | None = None,
    ) -> list[Job]:
        # Filter by queue_names if provided
        available = self._jobs
        if queue_names:
            available = [j for j in self._jobs if j.name in queue_names]

        claimed = available[:max_jobs]
        for job in claimed:
            self._jobs.remove(job)
        return claimed

    async def complete(self, job_id: UUID, result: JobResult) -> None:
        self.completed_jobs.append((job_id, result))

    async def requeue(self, job_id: UUID, delay_seconds: int | None = None) -> None:
        self.requeued_jobs.append((job_id, delay_seconds))


class FakeInboundEventRepository:
    """Fake InboundEventRepository supporting claim_batch for worker tests."""

    def __init__(self) -> None:
        self.storage: dict[str, InboundEvent] = {}  # key: provider_event_id
        self.claimed_events: list[InboundEvent] = []

    def exists_by_provider_id(self, provider_name: str, provider_event_id: str) -> bool:
        return provider_event_id in self.storage

    def add(self, entity: InboundEvent) -> None:
        self.storage[entity.provider_event_id] = entity

    def get_unprocessed(self, limit: int = 100) -> Sequence[InboundEvent]:
        return list(self.storage.values())[:limit]

    def get(self, event_id: UUID) -> InboundEvent | None:
        for ev in self.storage.values():
            if ev.id == event_id:
                return ev
        return None

    def save(self, entity: InboundEvent) -> None:
        self.storage[entity.provider_event_id] = entity

    def claim_batch(
        self,
        lease_seconds: int,
        batch_size: int = 10,
        now: datetime | None = None,
    ) -> Sequence[InboundEvent]:
        """Simulate claim_batch with SKIP LOCKED behavior."""
        from datetime import UTC, datetime

        if now is None:
            now = datetime.now(UTC)

        # Find unprocessed events that are not locked
        available = [
            ev
            for ev in self.storage.values()
            if not ev.processed and (ev.locked_until is None or ev.locked_until <= now)
        ]

        claimed = available[:batch_size]
        for ev in claimed:
            ev.claim(lease_seconds=lease_seconds, at=now)
            self.claimed_events.append(ev)

        return claimed


class FakeUnitOfWork(AbstractContextManager[UnitOfWork]):
    """Fake UnitOfWork for worker tests with fake inbound_events repository."""

    def __init__(
        self,
        inbound_repo: FakeInboundEventRepository,
        clock: Any,
    ) -> None:
        self.inbound_events = inbound_repo
        self._clock = clock
        self._committed = False
        self._rolled_back = False

    def __enter__(self) -> UnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        return False

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        self._rolled_back = True


class FakeHandleInboundCommand:
    """Fake HandleInboundCommand for worker tests."""

    def __init__(self, inbound_repo: FakeInboundEventRepository) -> None:
        self.inbound_repo = inbound_repo
        self.call_count = 0
        self.processed_events: list[InboundEvent] = []

    def execute(
        self,
        sender_phone: str,
        message_text: str,
        provider_message_id: str,
        at: datetime | None = None,
    ) -> None:
        self.call_count += 1
        # Find the event in the repo and mark as processed
        if provider_message_id in self.inbound_repo.storage:
            ev = self.inbound_repo.storage[provider_message_id]
            ev.mark_as_processed(at=at or datetime.now(UTC))
            self.processed_events.append(ev)


class FakeDispatcher:
    def dispatch_batch(self, batch_size: int) -> int:
        return 0


class FakeCadenceProcessor:
    def execute(self, batch_size: int) -> int:
        return 0


@pytest.mark.asyncio
async def test_worker_ingest_and_enrich_cycles(monkeypatch):
    """Verifica que os ciclos de ingestão e enriquecimento são executados periodicamente."""
    # Configura intervals curtos para teste
    monkeypatch.setattr(settings, "WORKER_POLL_INTERVAL_SECONDS", 1)
    monkeypatch.setattr(settings, "WORKER_INGEST_INTERVAL_SECONDS", 2)
    monkeypatch.setattr(settings, "WORKER_ENRICH_INTERVAL_SECONDS", 2)
    monkeypatch.setattr(settings, "KILL_SWITCH", False)
    monkeypatch.setattr(settings, "DRY_RUN", True)
    monkeypatch.setattr(settings, "AUTOMATION_ENABLED", True)
    monkeypatch.setattr(settings, "INGEST_SEARCH_QUERY", '{"location":"BR"}')

    fake_ingest = FakeIngestCommand()
    fake_enrich = FakeEnrichCommand()
    fake_queue = FakeJobQueue()

    # adiciona um job de enriquecimento
    class _Job:
        def __init__(self):
            self.id = UUID("12345678-1234-5678-1234-567812345678")
            self.name = "enrich_lead"
            self.payload = {"lead_id": "lead-1"}
            self.retry_count = 0
            self.max_retries = 3

    await fake_queue.enqueue(_Job())

    worker = Worker(poll_interval_seconds=1, batch_size=5)
    # substitui dependências por fakes
    worker._dispatcher = FakeDispatcher()
    worker._cadence_processor = FakeCadenceProcessor()
    worker._ingest_cmd = fake_ingest
    worker._enrich_cmd = fake_enrich
    worker._job_queue = fake_queue

    # Executa o loop por alguns segundos e depois sinaliza shutdown
    def stop_after():
        time.sleep(3)
        worker._shutdown = True

    import threading

    t = threading.Thread(target=stop_after)
    t.start()
    try:
        await worker.run()
    except SystemExit:
        pass
    t.join()

    # Ingest deve ter rodado ao menos uma vez (intervalo 2s, loop 3s)
    assert fake_ingest.call_count >= 1
    # Enriquecimento deve ter processado o job
    assert fake_enrich.call_count == 1


@pytest.mark.asyncio
async def test_worker_inbound_cycle_processes_events(monkeypatch):
    """Verifica que o ciclo de inbound processa eventos via claim_batch (SKIP LOCKED)."""
    monkeypatch.setattr(settings, "WORKER_POLL_INTERVAL_SECONDS", 1)
    monkeypatch.setattr(settings, "WORKER_INGEST_INTERVAL_SECONDS", 10)
    monkeypatch.setattr(settings, "WORKER_ENRICH_INTERVAL_SECONDS", 10)
    monkeypatch.setattr(settings, "KILL_SWITCH", False)
    monkeypatch.setattr(settings, "DRY_RUN", True)
    monkeypatch.setattr(settings, "AUTOMATION_ENABLED", True)

    fake_ingest = FakeIngestCommand()
    fake_enrich = FakeEnrichCommand()
    fake_queue = FakeJobQueue()
    fake_dispatcher = FakeDispatcher()
    fake_cadence = FakeCadenceProcessor()

    # Create fake inbound repo and add an event
    fake_inbound_repo = FakeInboundEventRepository()
    fake_clock = FakeClock()
    now = fake_clock.now()
    inbound_event = InboundEvent.create(
        provider_name="evolution",
        provider_event_id="msg-test-123",
        event_type="message",
        payload={
            "data": {
                "key": {"remoteJid": "5511999999999@s.whatsapp.net"},
                "message": {"conversation": "Olá"},
            }
        },
        at=now,
    )
    fake_inbound_repo.add(inbound_event)

    # Create fake handle inbound command
    fake_inbound_cmd = FakeHandleInboundCommand(fake_inbound_repo)

    # Create fake UoW factory
    fake_uow = FakeUnitOfWork(fake_inbound_repo, fake_clock)

    def fake_uow_factory():
        return fake_uow

    # Mock container's get_uow_factory
    import vendas.interfaces.worker.main as worker_module

    monkeypatch.setattr(worker_module.container, "get_uow_factory", lambda: fake_uow_factory)

    worker = Worker(poll_interval_seconds=1, batch_size=5)
    worker._dispatcher = fake_dispatcher
    worker._cadence_processor = fake_cadence
    worker._ingest_cmd = fake_ingest
    worker._enrich_cmd = fake_enrich
    worker._job_queue = fake_queue
    worker._inbound_cmd = fake_inbound_cmd

    # Executa o loop por alguns segundos e depois sinaliza shutdown
    def stop_after():
        time.sleep(3)
        worker._shutdown = True

    import threading

    t = threading.Thread(target=stop_after)
    t.start()
    try:
        await worker.run()
    except SystemExit:
        pass
    t.join()

    # Inbound cycle should have claimed and processed the event
    assert fake_inbound_cmd.call_count == 1
    assert len(fake_inbound_cmd.processed_events) == 1
    assert fake_inbound_cmd.processed_events[0].processed is True
    assert fake_inbound_cmd.processed_events[0].provider_event_id == "msg-test-123"


@pytest.mark.asyncio
async def test_worker_kill_switch_stops_immediately(monkeypatch):
    """KILL_SWITCH deve interromper o worker antes de qualquer ciclo."""
    monkeypatch.setattr(settings, "WORKER_POLL_INTERVAL_SECONDS", 1)
    monkeypatch.setattr(settings, "WORKER_INGEST_INTERVAL_SECONDS", 1)
    monkeypatch.setattr(settings, "WORKER_ENRICH_INTERVAL_SECONDS", 1)
    monkeypatch.setattr(settings, "KILL_SWITCH", True)
    monkeypatch.setattr(settings, "DRY_RUN", True)
    monkeypatch.setattr(settings, "AUTOMATION_ENABLED", True)

    worker = Worker(poll_interval_seconds=1, batch_size=5)
    worker._dispatcher = FakeDispatcher()
    worker._cadence_processor = FakeCadenceProcessor()
    worker._ingest_cmd = FakeIngestCommand()
    worker._enrich_cmd = FakeEnrichCommand()
    worker._job_queue = FakeJobQueue()

    # O loop deve sair imediatamente sem chamar comandos
    with pytest.raises(SystemExit):
        await worker.run()


if __name__ == "__main__":
    pytest.main([__file__])

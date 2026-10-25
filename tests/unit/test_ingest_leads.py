"""Unit tests for IngestLeadsCommand."""

from datetime import UTC, datetime
from typing import Any, Self
from uuid import UUID, uuid4

import pytest

from tests.fakes.fakes import FakeClock, FakeLeadSource, InMemoryLeadRepository
from vendas.application.commands.ingest_leads import IngestLeadsCommand
from vendas.domain.entities.lead import LeadStatus
from vendas.domain.ports import Job, JobQueue, UnitOfWork


class FakeJobQueue(JobQueue):
    """Fake JobQueue for tests."""

    def __init__(self) -> None:
        self.enqueued_jobs: list[Job] = []

    async def enqueue(self, job: Job) -> UUID:
        job_id = job.id if job.id != UUID(int=0) else uuid4()
        new_job = Job(
            id=job_id,
            name=job.name,
            payload=job.payload,
            priority=job.priority,
            scheduled_at=job.scheduled_at,
            max_retries=job.max_retries,
            retry_count=job.retry_count,
            timeout_seconds=job.timeout_seconds,
            created_at=job.created_at,
        )
        self.enqueued_jobs.append(new_job)
        return job_id

    async def enqueue_batch(self, jobs: list[Job]) -> list[UUID]:
        return [await self.enqueue(job) for job in jobs]

    async def dequeue(
        self,
        worker_id: str,
        max_jobs: int = 10,
        queue_names: list[str] | None = None,
    ) -> list[Job]:
        return []

    async def complete(self, job_id: UUID, result: Any) -> None:
        pass

    async def requeue(self, job_id: UUID, delay_seconds: int = 0) -> None:
        pass

    async def get_job(self, job_id: UUID) -> Job | None:
        return None

    async def cancel(self, job_id: UUID) -> bool:
        return False

    async def get_queue_stats(self, queue_name: str | None = None) -> dict[str, int]:
        return {"pending": 0, "processing": 0, "completed": 0, "failed": 0}


class FakeUnitOfWork(UnitOfWork):
    """Fake UnitOfWork for tests."""

    def __init__(self, lead_repo: InMemoryLeadRepository) -> None:
        self.leads = lead_repo
        self._committed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        self._committed = False

    def collect_events(self) -> list[Any]:
        return []


@pytest.fixture
def lead_repo() -> InMemoryLeadRepository:
    return InMemoryLeadRepository()


@pytest.fixture
def uow(lead_repo: InMemoryLeadRepository) -> FakeUnitOfWork:
    return FakeUnitOfWork(lead_repo)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))


@pytest.fixture
def job_queue() -> FakeJobQueue:
    return FakeJobQueue()


@pytest.fixture
def lead_source() -> FakeLeadSource:
    return FakeLeadSource()


def test_ingest_leads_creates_new_leads_with_status_new(
    uow: FakeUnitOfWork,
    clock: FakeClock,
    job_queue: FakeJobQueue,
    lead_source: FakeLeadSource,
) -> None:
    # Arrange
    lead_source.set_leads(
        [
            {
                "name": "Empresa Teste",
                "cnpj": "12345678000195",  # valid CNPJ
                "phone": "+5511999999999",
                "email": "teste@empresa.com",
            }
        ]
    )

    command = IngestLeadsCommand(
        uow=uow,
        lead_source=lead_source,
        clock=clock,
        job_queue=job_queue,
    )

    # Act
    count = command.execute({"query": "test"})

    # Assert
    assert count == 1
    assert uow._committed is True
    assert len(job_queue.enqueued_jobs) == 1
    assert job_queue.enqueued_jobs[0].name == "enrich_lead"

    # Verify lead persisted with status NEW
    leads = list(uow.leads.storage.values())
    assert len(leads) == 1
    lead = leads[0]
    assert lead.status == LeadStatus.NEW
    assert lead.name == "Empresa Teste"
    assert lead.cnpj is not None
    assert lead.cnpj.value == "12345678000195"
    assert lead.phone.value == "+5511999999999"
    assert lead.email is not None
    assert lead.email.value == "teste@empresa.com"


def test_ingest_leads_deduplicates_by_cnpj(
    uow: FakeUnitOfWork,
    clock: FakeClock,
    job_queue: FakeJobQueue,
    lead_source: FakeLeadSource,
) -> None:
    # Arrange: first ingestion
    lead_source.set_leads(
        [
            {
                "name": "Empresa Teste",
                "cnpj": "12345678000195",
                "phone": "+5511999999999",
                "email": "teste@empresa.com",
            }
        ]
    )
    command = IngestLeadsCommand(
        uow=uow,
        lead_source=lead_source,
        clock=clock,
        job_queue=job_queue,
    )
    command.execute({"query": "test"})

    # Second ingestion with same CNPJ but different phone
    lead_source.set_leads(
        [
            {
                "name": "Empresa Teste 2",
                "cnpj": "12345678000195",  # same CNPJ
                "phone": "+5511888888888",
                "email": "teste2@empresa.com",
            }
        ]
    )
    count = command.execute({"query": "test"})

    # Assert: no new lead created
    assert count == 0
    assert len(uow.leads.storage) == 1
    assert len(job_queue.enqueued_jobs) == 1  # only first enqueued


def test_ingest_leads_deduplicates_by_phone(
    uow: FakeUnitOfWork,
    clock: FakeClock,
    job_queue: FakeJobQueue,
    lead_source: FakeLeadSource,
) -> None:
    # Arrange: first ingestion
    lead_source.set_leads(
        [
            {
                "name": "Empresa Teste",
                "cnpj": "12345678000195",
                "phone": "+5511999999999",
                "email": "teste@empresa.com",
            }
        ]
    )
    command = IngestLeadsCommand(
        uow=uow,
        lead_source=lead_source,
        clock=clock,
        job_queue=job_queue,
    )
    command.execute({"query": "test"})

    # Second ingestion with same phone but different CNPJ
    lead_source.set_leads(
        [
            {
                "name": "Empresa Teste 2",
                "cnpj": "98765432000195",  # different CNPJ
                "phone": "+5511999999999",  # same phone
                "email": "teste2@empresa.com",
            }
        ]
    )
    count = command.execute({"query": "test"})

    # Assert: no new lead created
    assert count == 0
    assert len(uow.leads.storage) == 1
    assert len(job_queue.enqueued_jobs) == 1


def test_ingest_leads_skips_invalid_cnpj(
    uow: FakeUnitOfWork,
    clock: FakeClock,
    job_queue: FakeJobQueue,
    lead_source: FakeLeadSource,
) -> None:
    lead_source.set_leads(
        [
            {
                "name": "Empresa Invalida",
                "cnpj": "123",  # invalid CNPJ
                "phone": "+5511999999999",
                "email": "teste@empresa.com",
            }
        ]
    )
    command = IngestLeadsCommand(
        uow=uow,
        lead_source=lead_source,
        clock=clock,
        job_queue=job_queue,
    )
    count = command.execute({"query": "test"})

    assert count == 0
    assert len(uow.leads.storage) == 0
    assert len(job_queue.enqueued_jobs) == 0


def test_ingest_leads_skips_missing_phone(
    uow: FakeUnitOfWork,
    clock: FakeClock,
    job_queue: FakeJobQueue,
    lead_source: FakeLeadSource,
) -> None:
    lead_source.set_leads(
        [
            {
                "name": "Empresa Sem Telefone",
                "cnpj": "12345678000195",
                "phone": None,
                "email": "teste@empresa.com",
            }
        ]
    )
    command = IngestLeadsCommand(
        uow=uow,
        lead_source=lead_source,
        clock=clock,
        job_queue=job_queue,
    )
    count = command.execute({"query": "test"})

    assert count == 0
    assert len(uow.leads.storage) == 0
    assert len(job_queue.enqueued_jobs) == 0


def test_ingest_leads_multiple_leads(
    uow: FakeUnitOfWork,
    clock: FakeClock,
    job_queue: FakeJobQueue,
    lead_source: FakeLeadSource,
) -> None:
    lead_source.set_leads(
        [
            {
                "name": "Empresa 1",
                "cnpj": "12345678000195",
                "phone": "+5511999999999",
                "email": "empresa1@test.com",
            },
            {
                "name": "Empresa 2",
                "cnpj": "11222333000181",  # valid CNPJ
                "phone": "+5511988888888",  # valid mobile (ninth digit = 9)
                "email": "empresa2@test.com",
            },
        ]
    )
    command = IngestLeadsCommand(
        uow=uow,
        lead_source=lead_source,
        clock=clock,
        job_queue=job_queue,
    )
    count = command.execute({"query": "test"})

    assert count == 2
    assert len(uow.leads.storage) == 2
    assert len(job_queue.enqueued_jobs) == 2

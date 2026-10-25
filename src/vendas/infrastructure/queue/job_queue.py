"""In-memory JobQueue implementation for testing and development."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from vendas.domain.ports import Job, JobQueue, JobResult


@dataclass
class InMemoryJobQueue(JobQueue):
    """Simple in-memory job queue for testing."""

    _jobs: dict[UUID, Job] = field(default_factory=dict, init=False)
    _pending: list[UUID] = field(default_factory=list, init=False)
    _processing: set[UUID] = field(default_factory=set, init=False)
    _completed: dict[UUID, JobResult] = field(default_factory=dict, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def enqueue(self, job: Job) -> UUID:
        job_id = job.id
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
        async with self._lock:
            self._jobs[job_id] = new_job
            self._pending.append(job_id)
        return job_id

    async def enqueue_batch(self, jobs: Sequence[Job]) -> list[UUID]:
        return [await self.enqueue(job) for job in jobs]

    async def dequeue(
        self,
        worker_id: str,
        max_jobs: int = 10,
        queue_names: Sequence[str] | None = None,
    ) -> Sequence[Job]:
        async with self._lock:
            dequeued = []
            for _ in range(max_jobs):
                if not self._pending:
                    break
                job_id = self._pending.pop(0)
                job = self._jobs.get(job_id)
                if job:
                    self._processing.add(job_id)
                    dequeued.append(job)
            return dequeued

    async def complete(self, job_id: UUID, result: JobResult) -> None:
        async with self._lock:
            if job_id in self._processing:
                self._processing.remove(job_id)
                self._completed[job_id] = result

    async def requeue(self, job_id: UUID, delay_seconds: int = 0) -> None:
        async with self._lock:
            if job_id in self._processing:
                self._processing.remove(job_id)
            if job_id in self._jobs:
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
                self._pending.append(job_id)

    async def get_job(self, job_id: UUID) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def cancel(self, job_id: UUID) -> bool:
        async with self._lock:
            if job_id in self._pending:
                self._pending.remove(job_id)
                return True
            if job_id in self._processing:
                self._processing.remove(job_id)
                return True
            return False

    async def get_queue_stats(self, queue_name: str | None = None) -> dict[str, int]:
        async with self._lock:
            return {
                "pending": len(self._pending),
                "processing": len(self._processing),
                "completed": len(self._completed),
                "failed": sum(1 for r in self._completed.values() if not r.success),
            }

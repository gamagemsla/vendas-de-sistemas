"""Testes unitários para o worker de segundo plano."""

from __future__ import annotations

import time

import pytest

from vendas.bootstrap.settings import settings
from vendas.interfaces.worker.main import Worker


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
        self._jobs = []

    def enqueue(self, job) -> None:
        self._jobs.append(job)

    def dequeue(self):
        if self._jobs:
            return self._jobs.pop(0)
        return None


class FakeDispatcher:
    def dispatch_batch(self, batch_size: int) -> int:
        return 0


class FakeCadenceProcessor:
    def execute(self, batch_size: int) -> int:
        return 0


def test_worker_ingest_and_enrich_cycles(monkeypatch):
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
            self.name = "enrich_lead"
            self.payload = {"lead_id": "lead-1"}

    fake_queue.enqueue(_Job())

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
        worker.run()
    except SystemExit:
        pass
    t.join()

    # Ingest deve ter rodado ao menos uma vez (intervalo 2s, loop 3s)
    assert fake_ingest.call_count >= 1
    # Enriquecimento deve ter processado o job
    assert fake_enrich.call_count == 1


def test_worker_kill_switch_stops_immediately(monkeypatch):
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
        worker.run()


if __name__ == "__main__":
    pytest.main([__file__])

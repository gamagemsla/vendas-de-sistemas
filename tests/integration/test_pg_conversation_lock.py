"""Teste de integração para PgAdvisoryConversationLock (requer PostgreSQL)."""

import threading
import time
from uuid import uuid4

import pytest

from vendas.bootstrap.container import container


@pytest.mark.integration
def test_pg_advisory_conversation_lock_serializes():
    """Verifica que advisory lock serializa acessos concorrentes no mesmo lead."""
    # Only run if using PostgreSQL
    if "postgresql" not in container.engine.url.drivername:
        pytest.skip("PostgreSQL não configurado; pulando teste de advisory lock")

    lead_id = uuid4()
    results = []
    lock_factory = container.conversation_lock_factory

    def worker(idx: int):
        # each thread gets its own session via session_factory
        session = container.session_factory()
        try:
            lock = lock_factory(session)
            with lock.acquire(lead_id):
                time.sleep(0.02)
                results.append(idx)
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - start

    # Should be serialized ~0.06 seconds
    assert elapsed >= 0.05
    assert sorted(results) == [0, 1, 2]


@pytest.mark.integration
def test_pg_advisory_conversation_lock_different_leads_parallel():
    """Leads diferentes podem adquirir lock em paralelo."""
    if "postgresql" not in container.engine.url.drivername:
        pytest.skip("PostgreSQL não configurado; pulando teste de advisory lock")

    lead_a = uuid4()
    lead_b = uuid4()
    results = []
    lock_factory = container.conversation_lock_factory

    def worker_a():
        session = container.session_factory()
        try:
            lock = lock_factory(session)
            with lock.acquire(lead_a):
                time.sleep(0.02)
                results.append("a")
        finally:
            session.close()

    def worker_b():
        session = container.session_factory()
        try:
            lock = lock_factory(session)
            with lock.acquire(lead_b):
                time.sleep(0.02)
                results.append("b")
        finally:
            session.close()

    t1 = threading.Thread(target=worker_a)
    t2 = threading.Thread(target=worker_b)
    start = time.time()
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    elapsed = time.time() - start

    # Parallel -> ~0.02
    assert elapsed < 0.03
    assert set(results) == {"a", "b"}

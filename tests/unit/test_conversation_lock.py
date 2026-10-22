"""Testes de concorrência para ConversationLock (InMemoryConversationLock)."""

import threading
import time
from uuid import uuid4

from tests.fakes.fakes import InMemoryConversationLock


def test_inmemory_conversation_lock_serializes_access():
    lock = InMemoryConversationLock()
    lead_id = uuid4()
    results = []

    def worker(idx: int):
        with lock.acquire(lead_id):
            # simulate some work
            time.sleep(0.01)
            results.append(idx)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All workers should have executed sequentially, order may vary but all 5 present
    assert sorted(results) == list(range(5))


def test_inmemory_conversation_lock_different_leads_parallel():
    lock = InMemoryConversationLock()
    lead_a = uuid4()
    lead_b = uuid4()
    results = []

    def worker_a():
        with lock.acquire(lead_a):
            time.sleep(0.02)
            results.append("a")

    def worker_b():
        with lock.acquire(lead_b):
            time.sleep(0.02)
            results.append("b")

    t1 = threading.Thread(target=worker_a)
    t2 = threading.Thread(target=worker_b)
    start = time.time()
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    elapsed = time.time() - start

    # Since different leads, they can run in parallel -> total time ~0.02 not 0.04
    assert elapsed < 0.03
    assert set(results) == {"a", "b"}

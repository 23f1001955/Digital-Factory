import os
import json
import tempfile
import pytest
from orchestrator.concurrency import RunLock


def _lock_path(name: str) -> str:
    return os.path.join(tempfile.gettempdir(), name)


def test_acquire_and_release():
    path = _lock_path("test_runlock.json")
    if os.path.exists(path):
        os.remove(path)
    lock = RunLock(lock_path=path)
    assert lock.acquire("test-slug", mode="fail")
    assert lock.is_locked()
    lock.release()
    assert not lock.is_locked()


def test_acquire_fails_when_locked():
    path = _lock_path("test_runlock2.json")
    if os.path.exists(path):
        os.remove(path)
    lock1 = RunLock(lock_path=path)
    lock2 = RunLock(lock_path=path)
    assert lock1.acquire("slug-1", mode="fail")
    assert not lock2.acquire("slug-2", mode="fail")
    lock1.release()


def test_acquire_queues_when_locked():
    path = _lock_path("test_runlock3.json")
    if os.path.exists(path):
        os.remove(path)
    lock1 = RunLock(lock_path=path, poll_interval=0.1, max_wait=2)
    lock2 = RunLock(lock_path=path, poll_interval=0.1, max_wait=2)
    assert lock1.acquire("slug-1", mode="queue")
    assert not lock2.acquire("slug-2", mode="queue")
    lock1.release()


def test_clean_stale():
    path = _lock_path("test_runlock_stale.json")
    if os.path.exists(path):
        os.remove(path)
    info = {"slug": "stale", "pid": 99999, "start_time": "2000-01-01T00:00:00"}
    with open(path, "w") as f:
        json.dump(info, f)
    lock = RunLock(lock_path=path, stale_timeout_minutes=0)
    assert lock.clean_stale()
    assert not lock.is_locked()
    if os.path.exists(path):
        os.remove(path)


def test_ignores_mode_bypasses():
    path = _lock_path("test_runlock4.json")
    if os.path.exists(path):
        os.remove(path)
    lock1 = RunLock(lock_path=path)
    lock2 = RunLock(lock_path=path)
    assert lock1.acquire("slug-1", mode="fail")
    assert lock2.acquire("slug-2", mode="ignore")
    lock1.release()
    lock2.release()

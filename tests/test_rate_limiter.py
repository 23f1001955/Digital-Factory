import time
from orchestrator.rate_limiter import RateLimiter, ServiceConfig


def test_allows_calls_under_limit():
    rl = RateLimiter()
    rl.services["test"] = ServiceConfig(max_calls=5, window_seconds=10)
    for _ in range(5):
        waited = rl.wait_if_needed("test")
        rl.record_call("test")
        assert waited == 0.0


def test_blocks_when_over_limit():
    rl = RateLimiter()
    rl.services["test"] = ServiceConfig(max_calls=2, window_seconds=60)
    for _ in range(2):
        rl.wait_if_needed("test")
        rl.record_call("test")
    waited = rl.wait_if_needed("test")
    assert waited > 0


def test_resets_after_window():
    rl = RateLimiter()
    rl.services["test"] = ServiceConfig(max_calls=1, window_seconds=0.05)
    rl.wait_if_needed("test")
    rl.record_call("test")
    time.sleep(0.06)
    waited = rl.wait_if_needed("test")
    assert waited == 0.0


def test_unknown_service_does_not_block():
    rl = RateLimiter()
    waited = rl.wait_if_needed("nonexistent")
    assert waited == 0.0


def test_get_status_returns_counts():
    rl = RateLimiter()
    rl.services["a"] = ServiceConfig(max_calls=10, window_seconds=60)
    rl.record_call("a")
    status = rl.get_status()
    assert "a" in status
    assert status["a"]["recent_calls"] == 1
    assert status["a"]["remaining"] == 9
    assert status["a"]["max_calls"] == 10
    assert status["a"]["window_seconds"] == 60

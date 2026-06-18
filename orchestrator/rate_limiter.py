import time
import logging
from dataclasses import dataclass
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ServiceConfig:
    max_calls: int
    window_seconds: int


DEFAULT_SERVICES: Dict[str, ServiceConfig] = {
    "anthropic": ServiceConfig(max_calls=15, window_seconds=60),
    "openai": ServiceConfig(max_calls=20, window_seconds=60),
    "gumroad": ServiceConfig(max_calls=30, window_seconds=60),
    "etsy": ServiceConfig(max_calls=10, window_seconds=60),
    "shopify": ServiceConfig(max_calls=40, window_seconds=60),
    "stripe": ServiceConfig(max_calls=100, window_seconds=60),
}


class RateLimiter:
    def __init__(self, services: Dict[str, ServiceConfig] | None = None):
        self.services = services or dict(DEFAULT_SERVICES)
        self._windows: Dict[str, List[float]] = {}

    def wait_if_needed(self, service: str) -> float:
        cfg = self.services.get(service)
        if cfg is None:
            return 0.0
        if service not in self._windows:
            self._windows[service] = []
        now = time.monotonic()
        cutoff = now - cfg.window_seconds
        self._windows[service] = [t for t in self._windows[service] if t > cutoff]
        if len(self._windows[service]) >= cfg.max_calls:
            sleep_for = self._windows[service][0] + cfg.window_seconds - now
            if sleep_for > 0:
                logger.info("Rate limit hit for %s — sleeping %.2fs", service, sleep_for)
                time.sleep(sleep_for)
                self._windows[service] = [t for t in self._windows[service] if t > cutoff]
                return sleep_for
        return 0.0

    def record_call(self, service: str) -> None:
        if service not in self._windows:
            self._windows[service] = []
        self._windows[service].append(time.monotonic())

    def get_status(self) -> dict:
        now = time.monotonic()
        result = {}
        for svc, cfg in self.services.items():
            window = self._windows.get(svc, [])
            cutoff = now - cfg.window_seconds
            recent = len([t for t in window if t > cutoff])
            remaining = max(0, cfg.max_calls - recent)
            result[svc] = {
                "max_calls": cfg.max_calls,
                "window_seconds": cfg.window_seconds,
                "recent_calls": recent,
                "remaining": remaining,
            }
        return result

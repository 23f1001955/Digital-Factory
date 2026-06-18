import time
import json
import os as _os
import logging
from contextlib import contextmanager
from typing import Dict, List
from statistics import median

logger = logging.getLogger(__name__)


class BottleneckTracker:
    def __init__(self):
        self._timings: Dict[str, List[float]] = {}

    @contextmanager
    def track(self, category: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            if category not in self._timings:
                self._timings[category] = []
            self._timings[category].append(elapsed_ms)

    def report(self) -> dict:
        result = {}
        for cat, timings in self._timings.items():
            if not timings:
                continue
            sorted_t = sorted(timings)
            n = len(sorted_t)
            result[cat] = {
                "count": n,
                "p50_ms": round(median(sorted_t), 2),
                "p95_ms": round(sorted_t[int(n * 0.95)], 2),
                "p99_ms": round(sorted_t[int(n * 0.99)], 2),
                "total_ms": round(sum(sorted_t), 2),
            }
        return result

    def save_report(self, path: str) -> None:
        data = self.report()
        if data:
            _os.makedirs(_os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info("Bottleneck report saved to %s", path)

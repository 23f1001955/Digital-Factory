import os
import json
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RunLock:
    def __init__(self, lock_path: str = "outputs/_runlock.json", poll_interval: float = 5.0, max_wait: float = 300.0, stale_timeout_minutes: int = 30):
        self.lock_path = lock_path
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        self.stale_timeout_minutes = stale_timeout_minutes

    def acquire(self, slug: str, mode: str = "fail") -> bool:
        if mode == "ignore":
            return True
        if self.is_locked():
            if self._is_stale():
                logger.warning("RunLock: stale lock detected — cleaning up")
                self.clean_stale()
            elif mode == "fail":
                logger.warning("RunLock: another run is active — aborting")
                return False
            elif mode == "queue":
                waited = 0.0
                while self.is_locked() and waited < self.max_wait:
                    time.sleep(self.poll_interval)
                    waited += self.poll_interval
                    if self._is_stale():
                        self.clean_stale()
                        break
                if self.is_locked():
                    logger.warning("RunLock: timed out waiting for lock")
                    return False
        self._write_lock(slug)
        logger.info("RunLock: acquired for %s (pid=%d)", slug, os.getpid())
        return True

    def release(self) -> None:
        if os.path.exists(self.lock_path):
            try:
                os.remove(self.lock_path)
                logger.info("RunLock: released")
            except OSError as e:
                logger.warning("RunLock: failed to release: %s", e)

    def is_locked(self) -> bool:
        if not os.path.exists(self.lock_path):
            return False
        try:
            with open(self.lock_path) as f:
                json.load(f)
            return True
        except (json.JSONDecodeError, OSError):
            return False

    def clean_stale(self) -> bool:
        if not self.is_locked():
            return True
        if self._is_stale():
            logger.info("RunLock: cleaning stale lock")
            self.release()
            return True
        return False

    def _write_lock(self, slug: str) -> None:
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        info = {"slug": slug, "pid": os.getpid(), "start_time": datetime.now(timezone.utc).isoformat()}
        with open(self.lock_path, "w") as f:
            json.dump(info, f)

    def _is_stale(self) -> bool:
        try:
            with open(self.lock_path) as f:
                info = json.load(f)
            start = datetime.fromisoformat(info["start_time"])
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            return elapsed > self.stale_timeout_minutes * 60
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            return False

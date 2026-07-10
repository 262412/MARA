from __future__ import annotations

import threading
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class _LockEntry:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.users = 0


_conversion_locks_guard = threading.Lock()
_conversion_locks: dict[tuple[str, str], _LockEntry] = {}


@contextmanager
def hold_conversion_lock(cache_dir: Path, signature: str) -> Iterator[None]:
    key = (str(cache_dir.resolve()), signature)
    with _conversion_locks_guard:
        entry = _conversion_locks.setdefault(key, _LockEntry())
        entry.users += 1

    entry.lock.acquire()
    try:
        yield
    finally:
        entry.lock.release()
        with _conversion_locks_guard:
            entry.users -= 1
            if entry.users == 0 and _conversion_locks.get(key) is entry:
                _conversion_locks.pop(key, None)


class _SharedConversionLimiter:
    """Coordinate converter capacity across all service instances in a process."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._active_limits: Counter[int] = Counter()
        self._waiting_limits: Counter[int] = Counter()
        self._active = 0

    @contextmanager
    def slot(self, requested_limit: int) -> Iterator[None]:
        limit = max(1, requested_limit)
        with self._condition:
            self._waiting_limits[limit] += 1
            try:
                while self._active >= self._effective_limit(limit):
                    self._condition.wait()
            except BaseException:
                self._remove_count(self._waiting_limits, limit)
                self._condition.notify_all()
                raise
            self._remove_count(self._waiting_limits, limit)
            self._active += 1
            self._active_limits[limit] += 1

        try:
            yield
        finally:
            with self._condition:
                self._active -= 1
                self._remove_count(self._active_limits, limit)
                self._condition.notify_all()

    def _effective_limit(self, requested_limit: int) -> int:
        limits = [requested_limit]
        limits.extend(self._active_limits)
        limits.extend(self._waiting_limits)
        return min(limits)

    @staticmethod
    def _remove_count(counter: Counter[int], limit: int) -> None:
        counter[limit] -= 1
        if counter[limit] <= 0:
            counter.pop(limit, None)


shared_conversion_limiter = _SharedConversionLimiter()

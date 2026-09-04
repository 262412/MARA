from __future__ import annotations

import pytest


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
def test_interrupted_lock_acquire_releases_registry_user(
    monkeypatch, tmp_path, interruption
):
    import ktem.preview.coordination as coordination

    class InterruptedLock:
        def acquire(self):
            raise interruption

        def release(self):
            raise AssertionError("an unacquired lock must not be released")

    class InterruptedEntry:
        def __init__(self):
            self.lock = InterruptedLock()
            self.users = 0

    cache_dir = tmp_path / "cache"
    signature = "interrupted-acquire"
    key = (str(cache_dir.resolve()), signature)
    monkeypatch.setattr(coordination, "_LockEntry", InterruptedEntry)
    try:
        with pytest.raises(interruption):
            with coordination.hold_conversion_lock(cache_dir, signature):
                pytest.fail("an interrupted acquire cannot enter the lock context")

        assert key not in coordination._conversion_locks
    finally:
        coordination._conversion_locks.pop(key, None)

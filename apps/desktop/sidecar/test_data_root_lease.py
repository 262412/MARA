from __future__ import annotations

import json
import multiprocessing
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from .data_root_lease import (
    DesktopDataRootLease,
    DesktopDataRootLeaseError,
    DesktopDataRootLockedError,
)


def _try_acquire(data_root: str, result: multiprocessing.Queue) -> None:
    try:
        with DesktopDataRootLease.acquire(Path(data_root)):
            result.put("acquired")
    except DesktopDataRootLockedError as error:
        result.put(error.code)


class DesktopDataRootLeaseTest(unittest.TestCase):
    def test_second_process_fails_closed_and_stale_metadata_is_recoverable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory)
            lease = DesktopDataRootLease.acquire(data_root)
            context = multiprocessing.get_context("spawn")
            result = context.Queue()
            process = context.Process(
                target=_try_acquire,
                args=(str(data_root), result),
            )
            process.start()
            process.join(timeout=10)
            self.assertEqual(process.exitcode, 0)
            self.assertEqual(result.get(timeout=2), "desktop_data_root_locked")

            lease.release()
            with DesktopDataRootLease.acquire(data_root) as recovered:
                self.assertTrue(recovered.acquired)

    def test_two_leases_in_one_process_cannot_both_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory)
            with DesktopDataRootLease.acquire(data_root):
                with self.assertRaises(DesktopDataRootLockedError):
                    DesktopDataRootLease.acquire(data_root)

    def test_repeated_acquisition_replaces_one_valid_process_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory)
            lease_path = data_root / "state" / ".sidecar-writer.lock"

            for _ in range(3):
                with DesktopDataRootLease.acquire(data_root):
                    pass
                identity = json.loads(lease_path.read_text(encoding="ascii"))
                self.assertEqual(identity["pid"], multiprocessing.current_process().pid)
                self.assertEqual(len(identity["identity"]), 32)

            self.assertLess(lease_path.stat().st_size, 128)

    def test_two_threads_racing_for_one_data_root_have_one_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory)
            barrier = threading.Barrier(2)
            release_winner = threading.Event()
            outcomes: list[str] = []
            outcomes_lock = threading.Lock()

            def acquire() -> None:
                barrier.wait()
                try:
                    with DesktopDataRootLease.acquire(data_root):
                        with outcomes_lock:
                            outcomes.append("acquired")
                        release_winner.wait(timeout=2)
                except DesktopDataRootLockedError:
                    with outcomes_lock:
                        outcomes.append("desktop_data_root_locked")
                    release_winner.set()

            threads = [threading.Thread(target=acquire) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

            self.assertEqual(
                sorted(outcomes),
                ["acquired", "desktop_data_root_locked"],
            )
            self.assertTrue(all(not thread.is_alive() for thread in threads))

    def test_unwritable_data_root_fails_with_a_stable_path_free_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.object(Path, "mkdir", side_effect=PermissionError("private")):
                with self.assertRaises(DesktopDataRootLeaseError) as caught:
                    DesktopDataRootLease.acquire(Path(temporary_directory))

            self.assertEqual(caught.exception.code, "desktop_data_root_unwritable")
            self.assertNotIn("private", caught.exception.message)


if __name__ == "__main__":
    unittest.main()

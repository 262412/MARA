from __future__ import annotations

import errno
import json
import multiprocessing
import os
import stat
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from .query_task_journal import (
    JsonQueryTaskJournal,
    QueryTaskPersistenceError,
    _persistence_error,
    _post_failure_probe,
    _write_synced_file,
    persistence_diagnostic,
)


def _crash_during_save(path_value: str, stage: str) -> None:
    path = Path(path_value)
    replacement: Any

    def crash_while_writing(temporary_path: Path, _payload: bytes) -> None:
        temporary_path.write_bytes(b'{"journal_version":2')
        os._exit(91)

    def crash_while_flushing(_descriptor: int) -> None:
        os._exit(94)

    def crash_before_replace(_source: Path, _destination: Path) -> None:
        os._exit(92)

    def crash_after_replace(source: Path, destination: Path) -> None:
        os.replace(source, destination)
        os._exit(93)

    if stage == "write":
        target = "sidecar.query_task_journal._write_synced_file"
        replacement = crash_while_writing
    elif stage == "flush":
        target = "sidecar.query_task_journal.os.fsync"
        replacement = crash_while_flushing
    else:
        target = "sidecar.query_task_journal._replace_with_bounded_retry"
        replacement = (
            crash_after_replace if stage == "after_replace" else crash_before_replace
        )
    with patch(target, side_effect=replacement):
        JsonQueryTaskJournal(path).save(
            {"journal_version": 2, "tasks": [{"task_id": "new-task"}]}
        )


def _os_error(
    error_number: int,
    *,
    winerror: int | None = None,
) -> OSError:
    error = OSError(error_number, "private path and secret sentinel")
    if winerror is not None:
        error.winerror = winerror  # type: ignore[attr-defined]
    return error


class QueryTaskJournalErrorContractTest(unittest.TestCase):
    def test_classifies_storage_faults_without_exposing_raw_errors(self) -> None:
        cases = (
            (_os_error(errno.ENOSPC, winerror=112), "query_storage_full", True),
            (_os_error(errno.EACCES, winerror=32), "query_state_locked", True),
            (_os_error(errno.EACCES, winerror=33), "query_state_locked", True),
            (
                _os_error(errno.EACCES, winerror=5),
                "query_state_replace_blocked",
                True,
            ),
            (_os_error(errno.EROFS), "query_state_read_only", True),
            (_os_error(errno.EISDIR), "query_state_corrupt", False),
        )

        for error, expected_code, expected_retryable in cases:
            with self.subTest(code=expected_code):
                classified = _persistence_error(error, operation="atomic_replace")
                self.assertEqual(classified.code, expected_code)
                self.assertEqual(classified.retryable, expected_retryable)
                self.assertEqual(classified.operation, "atomic_replace")
                self.assertNotIn("private", classified.message)
                self.assertNotIn("secret", classified.message)

    def test_access_denied_classification_depends_on_failed_operation(self) -> None:
        expected = {
            "write_temp": "query_state_permission_denied",
            "flush": "query_persistence_failed",
            "atomic_replace": "query_state_replace_blocked",
            "load": "query_state_permission_denied",
        }
        for operation, code in expected.items():
            with self.subTest(operation=operation):
                error = _persistence_error(
                    _os_error(errno.EACCES, winerror=5),
                    operation=operation,
                )
                self.assertEqual(error.code, code)
                self.assertEqual(error.operation, operation)
                self.assertNotIn("private", error.message)

    def test_corrupt_journal_is_typed_and_never_replaced_or_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "query-tasks.json"
            original = b'{"journal_version": 1, broken'
            path.write_bytes(original)

            with self.assertRaises(QueryTaskPersistenceError) as caught:
                JsonQueryTaskJournal(path).load()

            self.assertEqual(caught.exception.code, "query_state_corrupt")
            self.assertEqual(caught.exception.operation, "load")
            self.assertEqual(path.read_bytes(), original)


class QueryTaskJournalAtomicityTest(unittest.TestCase):
    def test_post_failure_probe_distinguishes_write_and_flush_failures(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "query-tasks.json"
            for operation, expected in (
                ("write_temp", "write_blocked"),
                ("flush", "flush_blocked"),
            ):
                with self.subTest(operation=operation), patch(
                    "sidecar.query_task_journal._write_synced_file",
                    side_effect=QueryTaskPersistenceError(
                        "query_persistence_failed",
                        "Safe failure.",
                        operation=operation,
                    ),
                ):
                    self.assertEqual(_post_failure_probe(path), expected)

    def test_real_save_reports_write_flush_and_replace_access_denied(self) -> None:
        cases = (
            ("write_temp", "sidecar.query_task_journal.os.open"),
            ("flush", "sidecar.query_task_journal.os.fsync"),
            ("atomic_replace", "sidecar.query_task_journal.os.replace"),
        )
        for operation, target in cases:
            with self.subTest(
                operation=operation
            ), tempfile.TemporaryDirectory() as root:
                path = Path(root) / "query-tasks.json"
                with (
                    patch(
                        target,
                        side_effect=_os_error(errno.EACCES, winerror=5),
                    ),
                    patch("sidecar.query_task_journal.time.sleep"),
                    self.assertRaises(QueryTaskPersistenceError) as caught,
                ):
                    JsonQueryTaskJournal(path).save({"journal_version": 2, "tasks": []})

                error = caught.exception
                self.assertEqual(error.operation, operation)
                diagnostic = persistence_diagnostic(error)
                self.assertEqual(diagnostic["operation"], operation)
                self.assertEqual(diagnostic["errno"], errno.EACCES)
                self.assertEqual(diagnostic["winerror"], 5)
                self.assertNotIn(root, error.message)
                self.assertNotIn("private", json.dumps(diagnostic))

    def test_save_uses_unique_same_directory_temp_flush_and_fsync(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "query-tasks.json"
            replaced_from: list[Path] = []
            real_replace = os.replace

            def capture_replace(
                source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                destination: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            ) -> None:
                replaced_from.append(Path(os.fsdecode(source)))
                real_replace(source, destination)

            with (
                patch("sidecar.query_task_journal.os.fsync", wraps=os.fsync) as fsync,
                patch(
                    "sidecar.query_task_journal.os.replace",
                    side_effect=capture_replace,
                ),
            ):
                JsonQueryTaskJournal(path).save(
                    {"journal_version": 2, "tasks": [{"task_id": "task-1"}]}
                )

            self.assertGreaterEqual(fsync.call_count, 1)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8"))["tasks"][0]["task_id"],
                "task-1",
            )
            self.assertEqual(len(replaced_from), 1)
            temporary_path = replaced_from[0]
            self.assertEqual(temporary_path.parent, path.parent)
            self.assertIn(str(os.getpid()), temporary_path.name)
            self.assertNotEqual(temporary_path.name, "query-tasks.tmp")
            self.assertFalse(temporary_path.exists())

    def test_probe_exercises_replace_without_touching_the_real_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "query-tasks.json"
            original = b'{"journal_version": 1, "tasks": []}'
            path.write_bytes(original)

            JsonQueryTaskJournal(path).probe()

            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.glob("*.probe-*")), [])

    def test_windows_sharing_violation_has_bounded_retries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "query-tasks.json"
            real_replace = os.replace
            attempts = 0

            def sharing_then_replace(source: Path, destination: Path) -> None:
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise _os_error(errno.EACCES, winerror=32)
                real_replace(source, destination)

            with (
                patch(
                    "sidecar.query_task_journal.os.replace",
                    side_effect=sharing_then_replace,
                ),
                patch("sidecar.query_task_journal.time.sleep") as sleep,
            ):
                JsonQueryTaskJournal(path).save({"journal_version": 2, "tasks": []})

            self.assertEqual(attempts, 3)
            self.assertEqual(sleep.call_count, 2)
            loaded = JsonQueryTaskJournal(path).load()
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["tasks"], [])

    def test_exhausted_sharing_violation_preserves_locked_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "query-tasks.json"
            original = b'{"journal_version":2,"tasks":[]}'
            path.write_bytes(original)

            with (
                patch(
                    "sidecar.query_task_journal.os.replace",
                    side_effect=_os_error(errno.EACCES, winerror=32),
                ),
                patch("sidecar.query_task_journal.time.sleep"),
                self.assertRaises(QueryTaskPersistenceError) as caught,
            ):
                JsonQueryTaskJournal(path).save({"journal_version": 2, "tasks": []})

            self.assertEqual(caught.exception.code, "query_state_locked")
            self.assertEqual(caught.exception.operation, "atomic_replace")
            self.assertEqual(caught.exception.retry_count, 4)
            self.assertEqual(caught.exception.post_failure_probe, "not_run")
            self.assertEqual(path.read_bytes(), original)

    def test_windows_access_denied_replace_retries_complete_transactions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "query-tasks.json"
            original = {"journal_version": 2, "tasks": [{"task_id": "old"}]}
            path.write_text(json.dumps(original), encoding="utf-8")
            real_replace = os.replace
            temporary_paths: list[Path] = []
            attempts = 0

            def capture_write(temporary_path: Path, payload: bytes) -> None:
                temporary_paths.append(temporary_path)
                _write_synced_file(temporary_path, payload)

            def access_denied_then_replace(source: Path, destination: Path) -> None:
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise _os_error(errno.EACCES, winerror=5)
                real_replace(source, destination)

            with (
                patch(
                    "sidecar.query_task_journal._write_synced_file",
                    side_effect=capture_write,
                ),
                patch(
                    "sidecar.query_task_journal.os.replace",
                    side_effect=access_denied_then_replace,
                ),
                patch("sidecar.query_task_journal.time.sleep") as sleep,
            ):
                JsonQueryTaskJournal(path).save(
                    {"journal_version": 2, "tasks": [{"task_id": "new"}]}
                )

            self.assertEqual(attempts, 3)
            self.assertEqual(sleep.call_count, 2)
            self.assertEqual(len(temporary_paths), 3)
            self.assertEqual(len(set(temporary_paths)), 3)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8"))["tasks"][0]["task_id"],
                "new",
            )

    def test_exhausted_access_denied_replace_preserves_original_and_probes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "query-tasks.json"
            original = b'{"journal_version":2,"tasks":[{"task_id":"old"}]}'
            path.write_bytes(original)
            real_replace = os.replace

            def block_only_journal(source: Path, destination: Path) -> None:
                if Path(destination) == path:
                    raise _os_error(errno.EACCES, winerror=5)
                real_replace(source, destination)

            with (
                patch(
                    "sidecar.query_task_journal.os.replace",
                    side_effect=block_only_journal,
                ),
                patch("sidecar.query_task_journal.time.sleep"),
            ):
                with self.assertRaises(QueryTaskPersistenceError) as caught:
                    JsonQueryTaskJournal(path).save(
                        {"journal_version": 2, "tasks": [{"task_id": "new"}]}
                    )

            error = caught.exception
            self.assertEqual(error.code, "query_state_replace_blocked")
            self.assertEqual(error.operation, "atomic_replace")
            self.assertEqual(error.winerror, 5)
            self.assertGreater(error.retry_count, 0)
            self.assertEqual(error.post_failure_probe, "ready")
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.glob(".query-tasks.json.tmp-*")), [])

    def test_real_filesystem_save_exercises_open_flush_and_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "query-tasks.json"
            journal = JsonQueryTaskJournal(path)

            journal.save({"journal_version": 2, "tasks": []})
            journal.probe()

            self.assertEqual(journal.load(), {"journal_version": 2, "tasks": []})


class QueryTaskJournalFilesystemRecoveryTest(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows read-only attribute coverage")
    def test_windows_read_only_target_preserves_the_existing_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "query-tasks.json"
            original = b'{"journal_version":2,"tasks":[{"task_id":"old"}]}'
            path.write_bytes(original)
            path.chmod(stat.S_IREAD)
            try:
                with self.assertRaises(QueryTaskPersistenceError) as caught:
                    JsonQueryTaskJournal(path).save(
                        {"journal_version": 2, "tasks": [{"task_id": "new"}]}
                    )
            finally:
                path.chmod(stat.S_IREAD | stat.S_IWRITE)

            self.assertEqual(caught.exception.code, "query_state_replace_blocked")
            self.assertEqual(caught.exception.operation, "atomic_replace")
            self.assertEqual(caught.exception.winerror, 5)
            self.assertEqual(caught.exception.post_failure_probe, "ready")
            self.assertEqual(path.read_bytes(), original)

    @unittest.skipUnless(os.name == "nt", "Windows external handle coverage")
    def test_windows_external_handle_preserves_the_existing_journal(self) -> None:
        import ctypes
        from ctypes import wintypes

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "query-tasks.json"
            original = b'{"journal_version":2,"tasks":[{"task_id":"old"}]}'
            path.write_bytes(original)
            kernel32 = getattr(ctypes, "WinDLL")("kernel32", use_last_error=True)
            kernel32.CreateFileW.argtypes = (
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            )
            kernel32.CreateFileW.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.CreateFileW(
                str(path),
                0x80000000,
                0x00000001,
                None,
                3,
                0x00000080,
                None,
            )
            self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
            try:
                with self.assertRaises(QueryTaskPersistenceError) as caught:
                    JsonQueryTaskJournal(path).save(
                        {"journal_version": 2, "tasks": [{"task_id": "new"}]}
                    )
            finally:
                self.assertTrue(kernel32.CloseHandle(handle))

            self.assertIn(
                caught.exception.code,
                {"query_state_locked", "query_state_replace_blocked"},
            )
            self.assertEqual(caught.exception.operation, "atomic_replace")
            self.assertIn(caught.exception.winerror, {5, 32, 33})
            self.assertEqual(caught.exception.retry_count, 4)
            self.assertEqual(path.read_bytes(), original)

    def test_process_termination_never_leaves_a_partial_target_journal(self) -> None:
        context = multiprocessing.get_context("spawn")
        for stage in ("write", "flush", "before_replace", "after_replace"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "query-tasks.json"
                original = {"journal_version": 2, "tasks": [{"task_id": "old"}]}
                path.write_text(json.dumps(original), encoding="utf-8")
                process = context.Process(
                    target=_crash_during_save,
                    args=(str(path), stage),
                )
                process.start()
                process.join(timeout=10)
                self.assertIn(process.exitcode, {91, 92, 93, 94})
                recovered = JsonQueryTaskJournal(path).load()
                self.assertIsInstance(recovered, dict)
                assert recovered is not None
                expected = "new-task" if stage == "after_replace" else "old"
                self.assertEqual(recovered["tasks"][0]["task_id"], expected)

    def test_directory_target_and_leftover_temp_never_delete_existing_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            path = root / "query-tasks.json"
            path.mkdir()
            leftover = root / ".query-tasks.json.tmp-legacy"
            leftover.write_text("preserve", encoding="utf-8")

            with self.assertRaises(QueryTaskPersistenceError) as caught:
                JsonQueryTaskJournal(path).load()

            self.assertEqual(caught.exception.code, "query_state_corrupt")
            self.assertTrue(path.is_dir())
            self.assertEqual(leftover.read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()

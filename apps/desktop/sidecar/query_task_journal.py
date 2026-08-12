from __future__ import annotations

import errno
import json
import os
import time
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

WINDOWS_SHARING_ERRORS = {32, 33}
WINDOWS_SHARING_RETRY_DELAYS = (0.02, 0.04, 0.08, 0.16)


class QueryTaskPersistenceError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = True,
        operation: str = "unknown",
        error_type: str = "QueryTaskPersistenceError",
        error_number: int | None = None,
        winerror: int | None = None,
        retry_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.operation = operation
        self.error_type = error_type
        self.error_number = error_number
        self.winerror = winerror
        self.retry_count = retry_count


class QueryTaskJournal(Protocol):
    def load(self) -> dict[str, Any] | None:
        ...

    def save(self, payload: dict[str, Any]) -> None:
        ...

    def probe(self) -> None:
        ...


class JsonQueryTaskJournal:
    def __init__(self, path: Path | None) -> None:
        self._path = path

    def load(self) -> dict[str, Any] | None:
        if self._path is None:
            return None
        try:
            if not self._path.exists():
                return None
            if self._path.is_dir():
                raise _corrupt_error(IsADirectoryError(), operation="load")
            raw = self._path.read_text(encoding="utf-8")
        except QueryTaskPersistenceError:
            raise
        except OSError as error:
            if self._path.is_dir():
                raise _corrupt_error(error, operation="load") from None
            raise _persistence_error(error, operation="load") from None
        try:
            payload = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise _corrupt_error(error, operation="load") from None
        if not isinstance(payload, dict):
            raise _corrupt_error(TypeError(), operation="load")
        return payload

    def save(self, payload: dict[str, Any]) -> None:
        if self._path is None:
            return
        try:
            serialized = json.dumps(payload, ensure_ascii=False, indent=2).encode(
                "utf-8"
            )
        except (TypeError, ValueError) as error:
            raise _corrupt_error(error, operation="write_temp") from None
        temporary_path = _unique_path(self._path, "tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.is_dir():
                raise _corrupt_error(
                    IsADirectoryError(),
                    operation="atomic_replace",
                )
            _write_synced_file(temporary_path, serialized)
            _replace_with_bounded_retry(temporary_path, self._path)
            _sync_directory(self._path.parent)
        except QueryTaskPersistenceError:
            raise
        except OSError as error:
            raise _persistence_error(error, operation="write_temp") from None
        finally:
            _remove_temporary(temporary_path)

    def probe(self) -> None:
        if self._path is None:
            return
        parent = self._path.parent
        source = _unique_path(self._path, "probe-source")
        destination = _unique_path(self._path, "probe-target")
        try:
            parent.mkdir(parents=True, exist_ok=True)
            _write_synced_file(source, b'{"probe":true}\n')
            _replace_with_bounded_retry(source, destination)
            _sync_directory(parent)
        except QueryTaskPersistenceError:
            raise
        except OSError as error:
            raise _persistence_error(error, operation="write_temp") from None
        finally:
            _remove_temporary(source)
            _remove_temporary(destination)


def _unique_path(path: Path, role: str) -> Path:
    return path.parent / f".{path.name}.{role}-{os.getpid()}-{uuid4().hex}"


def _write_synced_file(path: Path, payload: bytes) -> None:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as error:
        raise _persistence_error(error, operation="write_temp") from None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            try:
                stream.write(payload)
            except OSError as error:
                raise _persistence_error(error, operation="write_temp") from None
            try:
                stream.flush()
                os.fsync(stream.fileno())
            except OSError as error:
                raise _persistence_error(error, operation="flush") from None
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _replace_with_bounded_retry(source: Path, destination: Path) -> None:
    retry_count = 0
    while True:
        try:
            os.replace(source, destination)
            return
        except OSError as error:
            winerror = getattr(error, "winerror", None)
            if winerror not in WINDOWS_SHARING_ERRORS or retry_count >= len(
                WINDOWS_SHARING_RETRY_DELAYS
            ):
                raise _persistence_error(
                    error,
                    operation="atomic_replace",
                    retry_count=retry_count,
                ) from None
            time.sleep(WINDOWS_SHARING_RETRY_DELAYS[retry_count])
            retry_count += 1


def _sync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError as error:
        raise _persistence_error(error, operation="flush") from None
    try:
        os.fsync(descriptor)
    except OSError as error:
        raise _persistence_error(error, operation="flush") from None
    finally:
        os.close(descriptor)


def _remove_temporary(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _corrupt_error(
    error: BaseException,
    *,
    operation: str,
) -> QueryTaskPersistenceError:
    return QueryTaskPersistenceError(
        "query_state_corrupt",
        "MARA answer state is damaged and was left unchanged for recovery.",
        retryable=False,
        operation=operation,
        error_type=type(error).__name__,
    )


def _persistence_error(
    error: OSError,
    *,
    operation: str,
    retry_count: int = 0,
) -> QueryTaskPersistenceError:
    error_number = error.errno
    winerror = getattr(error, "winerror", None)
    if error_number == errno.ENOSPC or winerror == 112:
        return _classified_error(
            "query_storage_full",
            "MARA does not have enough free storage to save answer state.",
            error,
            operation=operation,
            retry_count=retry_count,
        )
    if winerror in WINDOWS_SHARING_ERRORS:
        return _classified_error(
            "query_state_locked",
            "Answer state is locked. Close any extra MARA instance, then retry.",
            error,
            operation=operation,
            retry_count=retry_count,
        )
    if error_number in {errno.EACCES, errno.EPERM} or winerror == 5:
        return _classified_error(
            "query_state_permission_denied",
            "MARA cannot write answer state until app data permissions are fixed.",
            error,
            operation=operation,
            retry_count=retry_count,
        )
    if error_number == errno.EROFS:
        return _classified_error(
            "query_state_read_only",
            "MARA app data is read-only and cannot save answer state.",
            error,
            operation=operation,
            retry_count=retry_count,
        )
    if error_number in {errno.EISDIR, errno.ENOTDIR}:
        return _classified_error(
            "query_state_corrupt",
            "MARA answer state has an invalid layout and was left unchanged.",
            error,
            retryable=False,
            operation=operation,
            retry_count=retry_count,
        )
    return _classified_error(
        "query_persistence_failed",
        "MARA could not safely save answer state.",
        error,
        operation=operation,
        retry_count=retry_count,
    )


def _classified_error(
    code: str,
    message: str,
    error: OSError,
    *,
    operation: str,
    retry_count: int,
    retryable: bool = True,
) -> QueryTaskPersistenceError:
    return QueryTaskPersistenceError(
        code,
        message,
        retryable=retryable,
        operation=operation,
        error_type=type(error).__name__,
        error_number=error.errno,
        winerror=getattr(error, "winerror", None),
        retry_count=retry_count,
    )

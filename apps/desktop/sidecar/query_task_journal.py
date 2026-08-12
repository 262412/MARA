from __future__ import annotations

import errno
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

WINDOWS_SHARING_ERRORS = {32, 33}
WINDOWS_TRANSIENT_REPLACE_ERRORS = {5, *WINDOWS_SHARING_ERRORS}
WINDOWS_REPLACE_RETRY_DELAYS = (0.02, 0.04, 0.08, 0.16)


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
        post_failure_probe: str = "not_run",
        smoke_mode: bool = False,
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
        self.post_failure_probe = post_failure_probe
        self.smoke_mode = smoke_mode


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
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.is_dir():
                raise _corrupt_error(
                    IsADirectoryError(),
                    operation="atomic_replace",
                )
            _save_with_bounded_retry(self._path, serialized)
            _sync_directory(self._path.parent)
        except QueryTaskPersistenceError:
            raise
        except OSError as error:
            raise _persistence_error(error, operation="write_temp") from None

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


def _save_with_bounded_retry(destination: Path, payload: bytes) -> None:
    retry_count = 0
    while True:
        source = _unique_path(destination, "tmp")
        try:
            _write_synced_file(source, payload)
            _replace_with_bounded_retry(source, destination)
            return
        except QueryTaskPersistenceError as error:
            transient_replace = (
                error.operation == "atomic_replace"
                and error.winerror in WINDOWS_TRANSIENT_REPLACE_ERRORS
            )
            if not transient_replace:
                raise
            if retry_count >= len(WINDOWS_REPLACE_RETRY_DELAYS):
                if error.winerror == 5:
                    probe_result = _post_failure_probe(destination)
                    raise _replace_failure_after_probe(
                        error,
                        retry_count=retry_count,
                        probe_result=probe_result,
                    ) from None
                raise _replace_retry_exhausted(error, retry_count) from None
            time.sleep(WINDOWS_REPLACE_RETRY_DELAYS[retry_count])
            retry_count += 1
        finally:
            _remove_temporary(source)


def _replace_with_bounded_retry(source: Path, destination: Path) -> None:
    try:
        os.replace(source, destination)
    except OSError as error:
        raise _persistence_error(error, operation="atomic_replace") from None


def _post_failure_probe(destination: Path) -> str:
    source = _unique_path(destination, "post-probe-source")
    target = _unique_path(destination, "post-probe-target")
    try:
        try:
            _write_synced_file(source, b'{"probe":true}\n')
        except QueryTaskPersistenceError as error:
            return "flush_blocked" if error.operation == "flush" else "write_blocked"
        try:
            _replace_with_bounded_retry(source, target)
        except QueryTaskPersistenceError:
            return "replace_blocked"
        try:
            _sync_directory(destination.parent)
        except QueryTaskPersistenceError:
            return "flush_blocked"
        return "ready"
    finally:
        _remove_temporary(source)
        _remove_temporary(target)


def _replace_failure_after_probe(
    error: QueryTaskPersistenceError,
    *,
    retry_count: int,
    probe_result: str,
) -> QueryTaskPersistenceError:
    if probe_result == "write_blocked":
        code = "query_state_permission_denied"
        message = "MARA cannot create answer checkpoints under the app data policy."
    else:
        code = "query_state_replace_blocked"
        message = (
            "The operating system temporarily blocked the answer state replacement."
        )
    return QueryTaskPersistenceError(
        code,
        message,
        retryable=True,
        operation="atomic_replace",
        error_type=error.error_type,
        error_number=error.error_number,
        winerror=error.winerror,
        retry_count=retry_count,
        post_failure_probe=probe_result,
        smoke_mode=error.smoke_mode,
    )


def _replace_retry_exhausted(
    error: QueryTaskPersistenceError,
    retry_count: int,
) -> QueryTaskPersistenceError:
    return QueryTaskPersistenceError(
        error.code,
        error.message,
        retryable=error.retryable,
        operation=error.operation,
        error_type=error.error_type,
        error_number=error.error_number,
        winerror=error.winerror,
        retry_count=retry_count,
        smoke_mode=error.smoke_mode,
    )


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
        if operation == "atomic_replace":
            return _classified_error(
                "query_state_replace_blocked",
                "The operating system blocked the answer state replacement.",
                error,
                operation=operation,
                retry_count=retry_count,
            )
        if operation == "flush":
            return _classified_error(
                "query_persistence_failed",
                "MARA could not flush the answer checkpoint safely.",
                error,
                operation=operation,
                retry_count=retry_count,
            )
        return _classified_error(
            "query_state_permission_denied",
            "MARA cannot create or read answer state under the app data policy.",
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


def persistence_diagnostic(error: QueryTaskPersistenceError) -> dict[str, Any]:
    values = (
        error.operation,
        error.error_number,
        error.winerror,
        error.retry_count,
        error.post_failure_probe,
        int(error.smoke_mode),
    )
    fingerprint = hashlib.sha256("|".join(map(str, values)).encode("ascii")).hexdigest()
    return {
        "operation": error.operation,
        "errno": error.error_number,
        "winerror": error.winerror,
        "retry_count": error.retry_count,
        "post_failure_probe": error.post_failure_probe,
        "smoke_mode": error.smoke_mode,
        "fingerprint": f"qpf-{fingerprint[:16]}",
    }

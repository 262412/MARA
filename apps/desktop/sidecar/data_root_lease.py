from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4


class DesktopDataRootLeaseError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DesktopDataRootLockedError(DesktopDataRootLeaseError):
    def __init__(self) -> None:
        super().__init__(
            "desktop_data_root_locked",
            "Another MARA Sidecar already owns this Desktop data directory.",
        )


class DesktopDataRootLease:
    _registry_lock = threading.Lock()
    _owned_paths: set[Path] = set()

    def __init__(self, path: Path, stream: BinaryIO) -> None:
        self._path = path
        self._stream = stream
        self.acquired = True

    @classmethod
    def acquire(cls, data_root: Path) -> "DesktopDataRootLease":
        resolved_root = data_root.expanduser().resolve()
        lease_path = resolved_root / "state" / ".sidecar-writer.lock"
        with cls._registry_lock:
            if lease_path in cls._owned_paths:
                raise DesktopDataRootLockedError()
            try:
                lease_path.parent.mkdir(parents=True, exist_ok=True)
                stream = lease_path.open("a+b")
            except OSError:
                raise DesktopDataRootLeaseError(
                    "desktop_data_root_unwritable",
                    "MARA cannot safely acquire its Desktop data directory.",
                ) from None
            try:
                _lock_stream(stream)
                _write_identity(stream)
            except BlockingIOError:
                stream.close()
                raise DesktopDataRootLockedError() from None
            except OSError as error:
                stream.close()
                if _is_lock_contention(error):
                    raise DesktopDataRootLockedError() from None
                raise DesktopDataRootLeaseError(
                    "desktop_data_root_unwritable",
                    "MARA cannot safely acquire its Desktop data directory.",
                ) from None
            cls._owned_paths.add(lease_path)
        return cls(lease_path, stream)

    def release(self) -> None:
        if not self.acquired:
            return
        self.acquired = False
        try:
            _unlock_stream(self._stream)
        finally:
            self._stream.close()
            with self._registry_lock:
                self._owned_paths.discard(self._path)

    def __enter__(self) -> "DesktopDataRootLease":
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.release()


def _write_identity(stream: BinaryIO) -> None:
    payload = json.dumps(
        {"pid": os.getpid(), "identity": uuid4().hex},
        separators=(",", ":"),
    ).encode("ascii")
    stream.seek(0)
    stream.write(payload)
    stream.truncate()
    stream.flush()
    os.fsync(stream.fileno())


def _lock_stream(stream: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(0)
        if stream.read(1) == b"":
            stream.seek(0)
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        msvcrt.locking(  # type: ignore[attr-defined]
            stream.fileno(),
            msvcrt.LK_NBLCK,  # type: ignore[attr-defined]
            1,
        )
        return

    import fcntl

    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_stream(stream: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(0)
        msvcrt.locking(  # type: ignore[attr-defined]
            stream.fileno(),
            msvcrt.LK_UNLCK,  # type: ignore[attr-defined]
            1,
        )
        return

    import fcntl

    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _is_lock_contention(error: OSError) -> bool:
    return getattr(error, "winerror", None) in {32, 33} or error.errno in {11, 13}

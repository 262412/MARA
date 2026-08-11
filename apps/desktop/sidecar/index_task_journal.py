from __future__ import annotations

import errno
import json
from pathlib import Path
from typing import Any, Protocol


class IndexTaskPersistenceError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class IndexTaskJournal(Protocol):
    def load(self) -> dict[str, Any] | None:
        ...

    def save(self, payload: dict[str, Any]) -> None:
        ...


class JsonIndexTaskJournal:
    def __init__(self, path: Path | None) -> None:
        self._path = path

    def load(self) -> dict[str, Any] | None:
        if self._path is None or not self._path.exists():
            return None
        return json.loads(self._path.read_text(encoding="utf-8"))

    def save(self, payload: dict[str, Any]) -> None:
        if self._path is None:
            return
        temporary_path = self._path.with_suffix(".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(self._path)
        except OSError as error:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise persistence_error_from(error) from None


def persistence_error_from(error: OSError) -> IndexTaskPersistenceError:
    if error.errno == errno.ENOSPC or getattr(error, "winerror", None) == 112:
        return IndexTaskPersistenceError(
            "index_storage_full",
            "MARA does not have enough free storage to save indexing state.",
            retryable=True,
        )
    return IndexTaskPersistenceError(
        "index_runtime_storage_unwritable",
        "MARA Desktop cannot write its indexing cache or state.",
        retryable=False,
    )

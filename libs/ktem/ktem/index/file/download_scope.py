"""A source snapshot for a single generated download, with short L1 leases."""

import json
from contextlib import contextmanager
from hashlib import sha256

from sqlalchemy import inspect

from ._selection_service import FileSelectionError
from .source_writes import source_lock


class DownloadScope:
    def __init__(self, selection, file_id, user_id):
        self.selection, self.file_id, self.user_id = selection, file_id, user_id
        self.engine, self.index = selection._engine, selection._index
        with self._lock():
            self.version = self._version()

    def _lock(self):
        return source_lock(self.engine, self.index._resources["Source"], self.file_id)

    def _version(self):
        row = self.selection._require_file_access(self.file_id, self.user_id)
        values = {
            column.key: getattr(row, column.key)
            for column in inspect(row).mapper.column_attrs
        }
        value = [
            self.engine.url.render_as_string(hide_password=True),
            row.__table__.fullname,
            self.index.id,
            values,
        ]
        return sha256(
            json.dumps(value, sort_keys=True, default=str).encode()
        ).hexdigest()

    @property
    def context(self):
        return {
            "source": self.version,
            "owner": str(self.user_id),
            "index": str(self.index.id),
        }

    @contextmanager
    def current(self):
        with self._lock():
            if self._version() != self.version:
                raise FileSelectionError("Download source changed during generation")
            yield

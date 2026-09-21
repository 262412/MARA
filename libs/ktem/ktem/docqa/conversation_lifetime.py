"""Short same-host conversation commits, shared across objects and processes.

Lock order when resources meet: sorted Source leases, content-path lease (if
needed), Conversation lease, then a fresh short SQL Session. Never acquire a
Source lease, call a model/indexer, yield, or join a worker under this lease.
This reuses L1's DB/table/ID namespace and persistent Windows lock inode. It is
not a multi-host fencing protocol. Existing authorization stays at each caller.
"""

from typing import Any

from filelock import FileLock
from ktem.db.models import Conversation
from ktem.index.file.source_writes import source_lock


def conversation_write(engine: Any, conversation_id: str) -> FileLock:
    return source_lock(engine, Conversation, str(conversation_id or "").strip())

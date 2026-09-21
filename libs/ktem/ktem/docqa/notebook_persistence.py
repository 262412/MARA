"""The short authorized Notebook transaction; record rules stay in the caller."""

from contextlib import contextmanager
from typing import Any, Callable, Iterator

from ktem.db.models import Conversation

from .conversation_lifetime import conversation_write


@contextmanager
def notebook_transaction(
    engine: Any,
    conversation_id: str,
    user_id: Any,
    *,
    session_factory: Callable,
    load_row: Callable,
    now: Callable,
) -> Iterator[Conversation]:
    with conversation_write(engine, conversation_id), session_factory(
        engine
    ) as session:
        row = load_row(session, conversation_id, user_id=user_id, access="write")
        yield row
        row.date_updated = now()
        session.add(row)
        session.commit()

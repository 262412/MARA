from __future__ import annotations

from typing import Callable

import gradio as gr
import pandas as pd
from ktem.db.engine import engine
from ktem.db.models import Conversation
from sqlalchemy import select
from sqlalchemy.orm import Session

_EMPTY_FILE_ROWS = [
    {
        "id": "-",
        "name": "-",
        "size": "-",
        "tokens": "-",
        "loader": "-",
        "conversations": "-",
        "date_created": "-",
    }
]


def normalize_selected_ids_from_payload(selected_payload) -> list[str]:
    if not isinstance(selected_payload, dict):
        return []

    selected_ids: list[str] = []
    for value in selected_payload.values():
        values = value if isinstance(value, list) else [value]
        for candidate in values:
            nested_values = candidate if isinstance(candidate, list) else [candidate]
            for nested in nested_values:
                if isinstance(nested, (dict, tuple, list)):
                    continue
                item = str(nested or "").strip()
                if not item or item.lower() in {"select", "upload", "all"}:
                    continue
                selected_ids.append(item)

    merged: list[str] = []
    seen = set()
    for item in selected_ids:
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def extract_conversation_file_ids(data_source: dict | None) -> list[str]:
    if not isinstance(data_source, dict):
        return []

    graph_ids = data_source.get("graph_source_ids", [])
    if isinstance(graph_ids, list):
        cleaned: list[str] = []
        seen = set()
        for value in graph_ids:
            file_id = str(value or "").strip()
            if not file_id or file_id in seen:
                continue
            seen.add(file_id)
            cleaned.append(file_id)
        if cleaned:
            return cleaned

    return normalize_selected_ids_from_payload(data_source.get("selected", {}))


def format_conversation_scope(conversation_names: list[str]) -> str:
    if not conversation_names:
        return "-"
    if len(conversation_names) <= 2:
        return ", ".join(conversation_names)
    return (
        f"{conversation_names[0]}, {conversation_names[1]} "
        f"(+{len(conversation_names) - 2})"
    )


class FileIndexListingController:
    def __init__(
        self,
        index,
        format_size_human_readable: Callable[[float | str, str], str],
    ) -> None:
        self._index = index
        self._format_size_human_readable = format_size_human_readable

    def _list_source_ids_for_user(self, user_id) -> list[str]:
        Source = self._index._resources.get("Source")
        if Source is None:
            return []

        with Session(engine) as session:
            statement = select(Source.id)
            if self._index.config.get("private", False):
                statement = statement.where(Source.user == user_id)
            rows = session.execute(statement).all()

        source_ids: list[str] = []
        for row in rows:
            file_id = str(row[0] or "").strip() if row else ""
            if file_id:
                source_ids.append(file_id)
        return source_ids

    def snapshot_source_ids(self, user_id) -> list[str]:
        return self._list_source_ids_for_user(user_id)

    def collect_new_source_ids(self, before_source_ids, user_id) -> list[str]:
        before_set = {
            str(item or "").strip()
            for item in (before_source_ids or [])
            if str(item or "").strip()
        }
        current_ids = self._list_source_ids_for_user(user_id)
        return [file_id for file_id in current_ids if file_id not in before_set]

    def list_file(self, user_id, name_pattern=""):
        if user_id is None:
            return [], pd.DataFrame.from_records(_EMPTY_FILE_ROWS)

        Source = self._index._resources["Source"]
        with Session(engine) as session:
            statement = select(Source)
            if self._index.config.get("private", False):
                statement = statement.where(Source.user == user_id)
            if name_pattern:
                statement = statement.where(Source.name.ilike(f"%{name_pattern}%"))

            conversation_statement = select(Conversation)
            if self._index.config.get("private", False):
                conversation_statement = conversation_statement.where(
                    Conversation.user == user_id
                )

            file_to_conversations: dict[str, list[str]] = {}
            for (conversation_row,) in session.execute(conversation_statement).all():
                conversation_name = str(conversation_row.name or conversation_row.id)
                for file_id in extract_conversation_file_ids(
                    conversation_row.data_source or {}
                ):
                    names = file_to_conversations.setdefault(file_id, [])
                    if conversation_name not in names:
                        names.append(conversation_name)

            results = [
                {
                    "id": each[0].id,
                    "name": each[0].name,
                    "size": self._format_size_human_readable(each[0].size, "B"),
                    "tokens": self._format_size_human_readable(
                        each[0].note.get("tokens", "-"), ""
                    ),
                    "loader": each[0].note.get("loader", "-"),
                    "conversations": format_conversation_scope(
                        file_to_conversations.get(each[0].id, [])
                    ),
                    "date_created": each[0].date_created.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for each in session.execute(statement).all()
            ]

        if results:
            return results, pd.DataFrame.from_records(results)
        return [], pd.DataFrame.from_records(_EMPTY_FILE_ROWS)

    @staticmethod
    def list_file_names(file_list_state):
        if file_list_state:
            file_names = [(item["name"], item["id"]) for item in file_list_state]
        else:
            file_names = []

        return gr.update(choices=file_names)

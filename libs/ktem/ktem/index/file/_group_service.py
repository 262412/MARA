from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

MAX_FILENAME_LENGTH = 20


class GroupServiceError(ValueError):
    pass


class FileGroupService:
    def __init__(self, *, index: Any, engine: Any) -> None:
        self._index = index
        self._engine = engine

    def list_groups(self, user_id: Any, file_list: Any):
        file_id_to_name = (
            {item["id"]: item["name"] for item in file_list} if file_list else {}
        )
        if user_id is None:
            return [], _empty_group_frame()

        group_table = self._index._resources["FileGroup"]
        with Session(self._engine) as session:
            statement = select(group_table)
            if self._index.config.get("private", False):
                statement = statement.where(group_table.user == user_id)
            groups = [row[0] for row in session.execute(statement).all()]

        results = [_group_record(group) for group in groups]
        if not results:
            return [], _empty_group_frame()
        formatted = deepcopy(results)
        for item in formatted:
            item["files"] = _format_group_files(item["files"], file_id_to_name)
        return results, pd.DataFrame.from_records(formatted)

    def selected_file_ids(self, group_id: str) -> list[str]:
        group_table = self._index._resources["FileGroup"]
        with Session(self._engine) as session:
            group = session.query(group_table).filter_by(id=group_id).first()
        if group is None:
            raise GroupServiceError("No group found")
        return [json.dumps(group.data["files"])]

    def save_group(
        self,
        group_id: str | None,
        group_name: str,
        group_files: list[str],
        user_id: Any,
    ) -> str:
        group_table = self._index._resources["FileGroup"]
        with Session(self._engine) as session:
            if group_id:
                group = session.query(group_table).filter_by(id=group_id).first()
                if group is None:
                    raise GroupServiceError("No group found")
                group.name = group_name
                group.data = {**dict(group.data or {}), "files": group_files}
            else:
                group = (
                    session.query(group_table)
                    .filter_by(name=group_name, user=user_id)
                    .first()
                )
                if group is not None:
                    raise GroupServiceError(f"Group {group_name} already exists")
                group = group_table(
                    name=group_name,
                    data={"files": group_files},
                    user=user_id,
                )
                session.add(group)
            session.commit()
            group_id = str(group.id)
        return group_id

    def delete_group(self, group_id: str | None) -> str:
        if not group_id:
            raise GroupServiceError("No group is selected")
        group_table = self._index._resources["FileGroup"]
        with Session(self._engine) as session:
            row = session.execute(
                select(group_table).where(group_table.id == group_id)
            ).first()
            if row is None:
                raise GroupServiceError("No group found")
            group = row[0]
            group_name = str(group.name)
            session.delete(group)
            session.commit()
        return group_name


def _group_record(group: Any) -> dict[str, Any]:
    return {
        "id": group.id,
        "name": group.name,
        "files": list(group.data.get("files", [])),
        "date_created": group.date_created.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _format_group_files(
    file_ids: list[str],
    file_id_to_name: dict[str, str],
) -> str:
    names = [file_id_to_name.get(file_id, "-") for file_id in file_ids]
    rendered = ", ".join(
        (
            f"'{name[:MAX_FILENAME_LENGTH]}..'"
            if len(name) > MAX_FILENAME_LENGTH
            else f"'{name}'"
        )
        for name in names
    )
    postfix = "s" if len(names) > 1 else ""
    return f"[{len(names)} item{postfix}] {rendered}"


def _empty_group_frame() -> pd.DataFrame:
    return pd.DataFrame.from_records(
        [{"id": "-", "name": "-", "files": "-", "date_created": "-"}]
    )


__all__ = ["FileGroupService", "GroupServiceError"]

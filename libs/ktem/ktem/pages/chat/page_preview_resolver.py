from __future__ import annotations

import json

from ktem.db.models import engine
from ktem.preview.context import PreviewAccess, preview_access_for_user
from ktem.preview.service import PreviewService

from .page_preview_runtime import ensure_pdf_preview_copy


class PreviewFileResolver:
    def __init__(self, app, file_name_cache: dict[str, str]):
        self._app = app
        self._file_name_cache = file_name_cache
        self._service = PreviewService(app, engine=engine)

    @staticmethod
    def extract_first_selected_file_id(selected_file_ids):
        if not selected_file_ids:
            return ""
        selected = selected_file_ids[0]
        if isinstance(selected, str) and selected.startswith("["):
            try:
                selected_items = json.loads(selected)
            except (TypeError, ValueError):
                return ""
            return selected_items[0] if selected_items else ""
        return selected

    def resolve_source(self, file_id: str, *, access: PreviewAccess | None = None):
        resolved = self._service.resolve_source(
            file_id,
            access=access or preview_access_for_user(self._app),
        )
        self._file_name_cache[file_id] = resolved.name
        return resolved

    def resolve_sources(
        self,
        file_ids,
        *,
        access: PreviewAccess | None = None,
        strict: bool = True,
    ):
        resolved = self._service.resolve_sources(
            file_ids,
            access=access or preview_access_for_user(self._app),
            strict=strict,
        )
        self._file_name_cache.update(
            {source.file_id: source.name for source in resolved}
        )
        return resolved

    def resolve_file_path_by_id(
        self, file_id: str, *, access: PreviewAccess | None = None
    ) -> str:
        if not file_id:
            return ""
        return str(self.resolve_source(file_id, access=access).path)

    def resolve_file_name_by_id(
        self, file_id: str, *, access: PreviewAccess | None = None
    ) -> str:
        if not file_id:
            return ""
        return self.resolve_source(file_id, access=access).name

    def resolve_selected_file(
        self,
        first_selector_choices,
        selected_file_ids,
        *,
        access: PreviewAccess | None = None,
    ):
        del first_selector_choices
        file_id = self.extract_first_selected_file_id(selected_file_ids)
        if not file_id:
            return "", "", ""
        source = self.resolve_source(str(file_id), access=access)
        path = ensure_pdf_preview_copy(str(source.path), source.name)
        return source.file_id, source.name, path

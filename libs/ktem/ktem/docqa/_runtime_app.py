from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class _RuntimeAppContext:
    def __init__(self):
        from ktem.settings import BaseSettingGroup, SettingGroup, SettingReasoningGroup
        from theflow.settings import settings as flowsettings

        self.dev_mode = getattr(flowsettings, "KH_MODE", "") == "dev"
        self.app_name = getattr(flowsettings, "KH_APP_NAME", "Kotaemon")
        self.app_version = getattr(flowsettings, "KH_APP_VERSION", "")
        self.f_user_management = getattr(
            flowsettings, "KH_FEATURE_USER_MANAGEMENT", False
        )
        self.default_settings = SettingGroup(
            application=BaseSettingGroup(settings=flowsettings.SETTINGS_APP),
            reasoning=SettingReasoningGroup(settings=flowsettings.SETTINGS_REASONING),
        )
        self._callbacks: dict[str, list] = {}
        self._events: dict[str, list] = {}

        self.register_extensions()
        self.register_reasonings()
        self.initialize_indices()
        self.default_settings.reasoning.finalize()
        self.default_settings.index.finalize()

    def initialize_indices(self):
        from ktem.index import IndexManager
        from ktem.settings import BaseSettingGroup

        self.index_manager = IndexManager(self)
        self.index_manager.on_application_startup()

        for index in self.index_manager.indices:
            options = index.get_user_settings()
            self.default_settings.index.options[index.id] = BaseSettingGroup(
                settings=options
            )

    def register_reasonings(self):
        from ktem.components import reasonings
        from ktem.settings import BaseSettingGroup
        from theflow.settings import settings as flowsettings
        from theflow.utils.modules import import_dotted_string

        if getattr(flowsettings, "KH_REASONINGS", None) is None:
            return

        for value in flowsettings.KH_REASONINGS:
            reasoning_cls = import_dotted_string(value, safe=False)
            rid = reasoning_cls.get_info()["id"]
            reasonings[rid] = reasoning_cls
            options = reasoning_cls().get_user_settings()
            self.default_settings.reasoning.options[rid] = BaseSettingGroup(
                settings=options
            )

    def register_extensions(self):
        import pluggy

        from ktem import extension_protocol
        from ktem.settings import BaseSettingGroup

        self.exman = pluggy.PluginManager("ktem")
        self.exman.add_hookspecs(extension_protocol)
        self.exman.load_setuptools_entrypoints("ktem")

        extension_declarations = self.exman.hook.ktem_declare_extensions()
        for extension_declaration in extension_declarations:
            functionality = extension_declaration["functionality"]
            if "reasoning" not in functionality:
                continue
            for rid, rdec in functionality["reasoning"].items():
                unique_rid = f"{extension_declaration['id']}/{rid}"
                self.default_settings.reasoning.options[unique_rid] = BaseSettingGroup(
                    settings=rdec["settings"],
                )

    def declare_event(self, name: str):
        self._events.setdefault(name, [])

    def subscribe_event(self, name: str, definition: dict):
        self._events.setdefault(name, []).append(definition)

    def get_event(self, name: str) -> list[dict]:
        return self._events.get(name, [])


class _DocQAPreviewService:
    def __init__(self, app):
        from ktem.docqa.preview_support import (
            OfficePreviewConversionService,
            PresentationTextService,
            PreviewFileResolver,
        )

        self._app = app
        self._file_name_cache: dict[str, str] = {}
        self._non_pdf_preview_cache: dict[str, list[str]] = {}
        self._total_pages_cache: dict[str, int] = {}
        self._resolver = PreviewFileResolver(app, self._file_name_cache)
        self._office_conversion = OfficePreviewConversionService(logger=logger)
        self._presentation_preview_service = PresentationTextService()

    def resolve_selected_file(
        self, selected_file_ids: list[str] | None
    ) -> tuple[str, str, str]:
        return self._resolver.resolve_selected_file(selected_file_ids or [])

    def resolve_file_path(self, file_id: str) -> str:
        return self._resolver.resolve_file_path_by_id(file_id)

    def resolve_file_name(self, file_id: str) -> str:
        return self._resolver.resolve_file_name_by_id(file_id)

    @staticmethod
    def _extract_pdf_page_text(
        pdf_path: str, page_number: int, max_chars: int = 7000
    ) -> str:
        if not pdf_path or not os.path.isfile(pdf_path):
            return ""
        from pypdf import PdfReader

        try:
            reader = PdfReader(pdf_path)
            if not reader.pages:
                return ""
            page_idx = max(0, min(len(reader.pages) - 1, int(page_number or 1) - 1))
            text = reader.pages[page_idx].extract_text() or ""
            text = " ".join(str(text).split())
            return text[:max_chars]
        except Exception:
            return ""

    def get_page_context_text(
        self,
        file_id: str,
        file_name: str,
        page_number: int,
        max_chars: int = 7000,
    ) -> str:
        from ktem.docqa.preview_support import (
            detect_office_extension,
            extract_docx_text,
            extract_xlsx_text,
            read_text_file,
        )

        if not file_id or not file_name:
            return ""

        source_path = self.resolve_file_path(file_id)
        if not source_path:
            return ""

        source_extension = detect_office_extension(file_name, source_path)
        file_extension = (Path(file_name).suffix or Path(source_path).suffix).lower()

        if file_extension == ".pdf":
            return self._extract_pdf_page_text(
                source_path, page_number, max_chars=max_chars
            )

        if source_extension in {".pptx", ".ppt"}:
            return self._presentation_preview_service.extract_slide_text(
                source_path,
                page_number,
                max_chars=max_chars,
            )

        if source_extension in {".docx", ".doc", ".xlsx", ".xls"}:
            cached_pdf = self._office_conversion.get_cached_pdf_preview(source_path)
            if not cached_pdf:
                cached_pdf = self._office_conversion.convert_to_pdf_preview(
                    source_path, file_name
                )
            if cached_pdf and os.path.isfile(cached_pdf):
                return self._extract_pdf_page_text(
                    cached_pdf, page_number, max_chars=max_chars
                )

        if file_extension in {".docx", ".doc"}:
            return extract_docx_text(source_path, max_chars=max_chars)
        if file_extension in {".xlsx", ".xls", ".csv"}:
            return extract_xlsx_text(source_path, max_chars=max_chars)
        if file_extension in {".txt", ".md", ".html", ".mhtml"}:
            return read_text_file(source_path, max_chars=max_chars)

        return ""

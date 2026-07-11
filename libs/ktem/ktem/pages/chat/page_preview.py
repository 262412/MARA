import logging
import os
from pathlib import Path
from typing import cast

import gradio as gr
from ktem.preview.context import PreviewAccess
from sqlmodel import Session, select

from kotaemon.loaders.pdf_loader import get_page_thumbnails

from ...db.models import engine
from . import page_preview_cache
from .generation_store import has_in_progress, make_page_key, set_current_view
from .page_preview_callbacks import (
    normalize_preview_tick,
    poll_office_conversion,
    resolve_preview_access,
)

# Import preview handlers for different file types
from .page_preview_document import (
    extract_docx_html,
    extract_docx_text,
    paginate_docx_html,
)
from .page_preview_models import PreviewPayloadRequest
from .page_preview_non_pdf import NonPdfPreviewService
from .page_preview_office import OfficePreviewConversionService
from .page_preview_presentation import PresentationPreviewService, extract_pptx_text
from .page_preview_resolver import PreviewFileResolver

# Import runtime utilities for PDF handling and page management
from .page_preview_runtime import (
    build_pdfjs_viewer_src,
    clamp_page,
    ensure_pdf_preview_copy,
    get_file_signature,
    is_valid_pdf,
    notice_html,
    safe_int,
    safe_pdf_page_count,
)
from .page_preview_service import PreviewPayloadService
from .page_preview_spreadsheet import extract_xlsx_text
from .page_preview_text import paginate_plain_text, read_text_file
from .page_preview_types import detect_office_extension, is_office_source, is_pdf_source

# Keep mindmap placeholder empty so the Knowledge Graph area is not occupied.
MINDMAP_PLACEHOLDER_HTML = ""
# Message shown when no answer is available yet
ANSWER_PLACEHOLDER_TEXT = "Ask a question about the current page to generate an answer."
logger = logging.getLogger(__name__)
_DIRECT_CALL_REQUEST = cast(gr.Request, object())


class ChatPagePreviewController:
    """Controller for managing page-level document preview and chat isolation.

    Handles document preview, page navigation, and maintains isolated chat history
    for each page of each file. Supports PDF, Office documents, and text files.
    """

    def __init__(self, app):
        self._app = app
        # Cache for page thumbnail images: {file_id: {page_num: thumbnail_base64}}
        self._page_thumbnail_cache: dict[str, dict[str, str]] = {}
        # Cache for page preview content: {file_id: {page_num: preview_html}}
        self._page_preview_cache: dict[str, dict[str, str]] = {}
        # Cache for total pages per file: {file_id: total_pages}
        self._total_pages_cache: dict[str, int] = {}
        # Cache for non-PDF file previews: {file_id: [page_html_list]}
        self._non_pdf_preview_cache: dict[str, list[str]] = {}
        # Cache for file names: {file_id: file_name}
        self._file_name_cache: dict[str, str] = {}
        # Resolver for locating and loading files
        self._file_resolver = PreviewFileResolver(app, self._file_name_cache)
        # Service for handling non-PDF file previews
        self._non_pdf_preview_service = NonPdfPreviewService(self)
        # Service for handling PowerPoint presentations
        self._presentation_preview_service = PresentationPreviewService(self)
        # Service for converting Office documents to PDF
        self._office_conversion = OfficePreviewConversionService(logger=logger)
        # Service for building preview payloads
        self._preview_payload_service = PreviewPayloadService(self)
        # Track last previewed file ID
        self._last_preview_file_id: str = ""
        # Track file that should force first page display
        self._force_first_page_file_id: str = ""
        # Track files that have shown Office placeholder
        self._office_placeholder_shown: set[str] = set()
        # Lock to prevent concurrent page changes: {file_id: locked}
        self._page_change_lock: dict[str, bool] = {}

    @staticmethod
    def _find_soffice_binary() -> str:
        return OfficePreviewConversionService.find_soffice_binary()

    @staticmethod
    def _is_pdf_source(file_name: str, file_path: str) -> bool:
        return is_pdf_source(file_name, file_path)

    @staticmethod
    def _detect_office_extension(file_name: str, file_path: str) -> str:
        return detect_office_extension(file_name, file_path)

    def _is_office_source(self, file_name: str, file_path: str) -> bool:
        return is_office_source(file_name, file_path)

    @staticmethod
    def _get_file_signature(file_path: str) -> str:
        return get_file_signature(file_path)

    def _get_pdfjs_viewer_src(
        self, file_path: str, page: int, fit_mode: str = "pdf"
    ) -> str:
        return build_pdfjs_viewer_src(file_path, page, fit_mode)

    def _get_page_thumbnail(self, file_id: str, page: int) -> str:
        if not file_id:
            return ""

        page_key = str(page)
        if file_id in self._page_thumbnail_cache:
            cached = self._page_thumbnail_cache[file_id].get(page_key)
            if cached is not None:
                return cached

        first_index = self._app.index_manager.indices[0]
        index_table = first_index._resources["Index"]
        doc_store = first_index._resources["DocStore"]

        with Session(engine) as session:
            stmt = select(index_table.target_id).where(
                index_table.source_id == file_id,
                index_table.relation_type == "document",
            )
            doc_ids = [row[0] for row in session.execute(stmt).all()]

        page_map: dict[str, str] = {}
        if doc_ids:
            docs = doc_store.get(doc_ids)
            for doc in docs:
                if doc.metadata.get("type") != "thumbnail":
                    continue
                page_label = str(doc.metadata.get("page_label", ""))
                image_origin = doc.metadata.get("image_origin", "")
                if page_label and image_origin:
                    page_map[page_label] = image_origin

        self._page_thumbnail_cache[file_id] = page_map
        return page_map.get(page_key, "")

    def _get_non_pdf_preview_src(
        self, file_id: str, file_name: str, file_path: str, page: int
    ) -> str:
        return self._non_pdf_preview_service.get_preview_src(
            file_id, file_name, file_path, page
        )

    def _resolve_file_path_by_file_id(
        self, file_id: str, *, access: PreviewAccess | None = None
    ) -> str:
        return self._file_resolver.resolve_file_path_by_id(file_id, access=access)

    def _resolve_file_name_by_file_id(
        self, file_id: str, *, access: PreviewAccess | None = None
    ) -> str:
        return self._file_resolver.resolve_file_name_by_id(file_id, access=access)

    @staticmethod
    def _paginate_plain_text(text: str, max_chars_per_page: int = 2200) -> list[str]:
        return paginate_plain_text(text, max_chars_per_page)

    @staticmethod
    def _paginate_docx_html(rich_html: str) -> list[str]:
        return paginate_docx_html(rich_html)

    @staticmethod
    def _read_text_file(file_path: str, max_chars: int = 9000) -> str:
        return read_text_file(file_path, max_chars)

    @staticmethod
    def _extract_docx_text(file_path: str, max_chars: int = 9000) -> str:
        return extract_docx_text(file_path, max_chars)

    @staticmethod
    def _extract_docx_html(file_path: str, max_chars: int = 12000) -> str:
        return extract_docx_html(file_path, max_chars)

    @staticmethod
    def _extract_pptx_text(file_path: str, max_chars: int = 9000) -> str:
        return extract_pptx_text(file_path, max_chars)

    @staticmethod
    def _extract_xlsx_text(file_path: str, max_chars: int = 9000) -> str:
        return extract_xlsx_text(file_path, max_chars)

    def _extract_text_from_file(self, file_path: str, file_name: str) -> str:
        return self._non_pdf_preview_service.extract_text_from_file(
            file_path, file_name
        )

    def _get_presentation_preview_src(
        self, file_id: str, file_path: str, page: int
    ) -> str:
        return self._presentation_preview_service.get_preview_src(
            file_id, file_path, page
        )

    def _get_page_preview_image(self, file_id: str, file_path: str, page: int) -> str:
        if not file_id or not file_path or not os.path.isfile(file_path):
            return ""

        page_key = str(page)
        if file_id in self._page_preview_cache:
            cached = self._page_preview_cache[file_id].get(page_key)
            if cached is not None:
                return cached

        page_map = self._page_preview_cache.setdefault(file_id, {})
        try:
            rendered_pages = get_page_thumbnails(
                Path(file_path), [max(0, page - 1)], dpi=120
            )
            if rendered_pages:
                page_map[page_key] = rendered_pages[0]
                return rendered_pages[0]
        except Exception as exc:
            logger.warning("Failed to render page preview: %s", exc)

        page_map[page_key] = ""
        return ""

    @staticmethod
    def _notice_html(message: str) -> str:
        return notice_html(message)

    @staticmethod
    def _safe_int(value, fallback: int = 1) -> int:
        return safe_int(value, fallback)

    def _safe_pdf_page_count(self, pdf_path: str, fallback: int = 1) -> int:
        return safe_pdf_page_count(pdf_path, fallback, logger=logger)

    def _get_office_job_status(self, file_path: str) -> str:
        return self._office_conversion.get_status(file_path)

    def _build_preview_payload(
        self,
        file_id: str,
        file_name: str,
        file_path: str,
        requested_page: int,
        known_total_pages: int = 1,
    ) -> tuple[int, int, str, str]:
        payload = self._preview_payload_service.build_payload(
            PreviewPayloadRequest(
                file_id=file_id,
                file_name=file_name,
                file_path=file_path,
                requested_page=requested_page,
                known_total_pages=known_total_pages,
            )
        )
        return (
            payload.page,
            payload.total_pages,
            payload.preview_src,
            payload.preview_notice,
        )

    def _get_pdf_preview_src_and_notice(
        self, file_id: str, file_name: str, file_path: str, page: int
    ) -> tuple[str, str]:
        _, _, preview_src, preview_notice = self._build_preview_payload(
            file_id, file_name, file_path, page, self._total_pages_cache.get(file_id, 1)
        )
        return preview_src, preview_notice

    def _extract_first_selected_file_id(self, selected_file_ids):
        return self._file_resolver.extract_first_selected_file_id(selected_file_ids)

    def _get_total_pages(self, file_id: str, file_name: str, file_path: str) -> int:
        _, total_pages, _, _ = self._build_preview_payload(
            file_id, file_name, file_path, 1, self._total_pages_cache.get(file_id, 1)
        )
        return total_pages

    @staticmethod
    def _clamp_page(page: int, total_pages: int) -> int:
        return clamp_page(page, total_pages)

    def _ensure_pdf_preview_copy(self, file_path: str, file_name: str) -> str:
        return ensure_pdf_preview_copy(file_path, file_name)

    def _convert_office_to_pdf_preview(self, file_path: str, file_name: str) -> str:
        return self._office_conversion.convert_to_pdf_preview(file_path, file_name)

    def _get_cached_office_pdf_preview(self, file_path: str) -> str:
        return self._office_conversion.get_cached_pdf_preview(file_path)

    @staticmethod
    def _is_valid_pdf(pdf_path: str) -> bool:
        return is_valid_pdf(pdf_path)

    def _schedule_office_pdf_conversion(self, file_path: str, file_name: str):
        self._office_conversion.schedule_conversion(file_path, file_name)

    def resolve_pdf_source(
        self,
        first_selector_choices,
        selected_file_ids,
        *,
        access: PreviewAccess | None = None,
    ):
        return self._file_resolver.resolve_selected_file(
            first_selector_choices, selected_file_ids, access=access
        )

    def is_office_file(self, file_name: str, file_path: str = "") -> bool:
        return self._is_office_source(file_name, file_path)

    def resolve_file_path(
        self, file_id: str, *, access: PreviewAccess | None = None
    ) -> str:
        return self._resolve_file_path_by_file_id(file_id, access=access)

    def resolve_sources(
        self,
        file_ids,
        *,
        access: PreviewAccess,
        strict: bool = True,
    ):
        return self._file_resolver.resolve_sources(
            file_ids, access=access, strict=strict
        )

    def _resolve_callback_source(self, file_id: str, request: gr.Request):
        source = self._file_resolver.resolve_source(
            file_id,
            access=resolve_preview_access(self._app, request, _DIRECT_CALL_REQUEST),
        )
        preview_path = ensure_pdf_preview_copy(str(source.path), source.name)
        return source.name, preview_path

    def get_cached_office_pdf(self, file_path: str) -> str:
        return self._get_cached_office_pdf_preview(file_path)

    def get_office_page_context_pdf_path(
        self,
        file_id: str,
        file_name: str,
    ) -> str:
        if not file_id or not file_name:
            return ""
        if not self.is_office_file(file_name, ""):
            return ""

        source_path = self.resolve_file_path(file_id)
        if not source_path:
            return ""
        return self.get_cached_office_pdf(source_path)

    def get_page_context_text(
        self,
        file_id: str,
        file_name: str,
        page_number: int,
        max_chars: int = 7000,
    ) -> str:
        if not file_id or not file_name:
            return ""

        source_path = self.resolve_file_path(file_id)
        if not source_path:
            return ""

        source_extension = self._detect_office_extension(file_name, source_path)
        if source_extension == ".pptx":
            return self._presentation_preview_service.extract_slide_text(
                source_path,
                page_number,
                max_chars=max_chars,
            )

        office_pdf = self.get_cached_office_pdf(source_path)
        if not office_pdf:
            return ""
        return office_pdf

    def clear_page_outputs(self):
        return (
            "",
            MINDMAP_PLACEHOLDER_HTML,
            gr.skip(),
            gr.skip(),
            ANSWER_PLACEHOLDER_TEXT,
            [],  # Empty chat history
        )

    def get_cached_page_outputs(
        self,
        page_outputs_cache: dict,
        page_number: int,
        file_id: str = "",
        session_key: str | None = None,
    ):
        return page_preview_cache.get_cached_page_outputs(
            page_outputs_cache,
            page_number,
            file_id,
            session_key=session_key,
            clear_page_outputs=self.clear_page_outputs,
            mindmap_placeholder=MINDMAP_PLACEHOLDER_HTML,
            answer_placeholder=ANSWER_PLACEHOLDER_TEXT,
        )

    def cache_page_outputs(
        self,
        page_outputs_cache: dict,
        page_number: int,
        last_question: str,
        mindmap_html: str,
        answer_text: str,
        file_id: str = "",
        chat_history: list | None = None,
    ):
        return page_preview_cache.cache_page_outputs(
            page_outputs_cache,
            page_number=page_number,
            last_question=last_question,
            mindmap_html=mindmap_html,
            answer_text=answer_text,
            file_id=file_id,
            chat_history=chat_history or [],
        )

    def on_selected_file_change(
        self,
        first_selector_choices,
        selected_file_ids,
        page_outputs_cache,
        request: gr.Request = _DIRECT_CALL_REQUEST,
    ):
        file_id, file_name, file_path = self.resolve_pdf_source(
            first_selector_choices,
            selected_file_ids,
            access=resolve_preview_access(self._app, request, _DIRECT_CALL_REQUEST),
        )
        self._force_first_page_file_id = file_id or ""
        if file_id:
            self._office_placeholder_shown.discard(file_id)
        (
            page_number,
            total_pages,
            preview_src,
            preview_notice,
        ) = self._build_preview_payload(file_id, file_name, file_path, 1, 1)
        session_key = getattr(request, "session_hash", None) or "default"
        if session_key:
            set_current_view(session_key, make_page_key(file_id, page_number))
        page_outputs = self.get_cached_page_outputs(
            page_outputs_cache, page_number, file_id, session_key=session_key
        )
        # Preserve page outputs cache for all files (don't clear it)
        # Only clear the current display if nothing cached
        return (
            file_id,
            file_name,
            file_path,
            page_number,
            total_pages,
            preview_src,
            preview_notice,
            *page_outputs,
            page_outputs_cache,  # Return the cache as-is to preserve all page data
        )

    def on_page_change(
        self,
        current_page,
        delta,
        file_id,
        file_path,
        page_outputs_cache,
        total_pages,
        request: gr.Request = _DIRECT_CALL_REQUEST,
    ):
        del file_path
        lock_key = file_id or "default"
        session_key = getattr(request, "session_hash", None) or "default"
        if session_key and has_in_progress(
            session_key, make_page_key(file_id, current_page)
        ):
            gr.Warning(
                "A response is still being generated for the current page. "
                "Switching pages won't stop it."
            )

        if self._page_change_lock.get(lock_key, False):
            logger.debug(
                f"Page change ignored for file {lock_key}, page={current_page}, delta={delta}"
            )
            # Return gr.skip() for all 10 outputs to match the expected output count
            return (
                gr.skip(),  # page_number
                gr.skip(),  # total_pages
                gr.skip(),  # preview_src
                gr.skip(),  # preview_notice
                gr.skip(),  # last_question
                gr.skip(),  # info_panel
                gr.skip(),  # plot_panel
                gr.skip(),  # state_plot_panel
                gr.skip(),  # answer_panel
                gr.skip(),  # chatbot
            )

        try:
            self._page_change_lock[lock_key] = True

            if not file_id:
                (
                    _,
                    total_pages,
                    preview_src,
                    preview_notice,
                ) = self._build_preview_payload(file_id, "", "", 1, 1)
                if session_key:
                    set_current_view(session_key, make_page_key(file_id, 1))
                return (
                    1,
                    total_pages,
                    preview_src,
                    preview_notice,
                    *self.get_cached_page_outputs(
                        page_outputs_cache,
                        1,
                        file_id,
                        session_key=session_key,
                    ),
                )

            file_name, file_path = self._resolve_callback_source(file_id, request)
            requested_page = int(current_page or 1) + int(delta or 0)
            (
                next_page,
                total_pages,
                preview_src,
                preview_notice,
            ) = self._build_preview_payload(
                file_id,
                file_name,
                file_path,
                requested_page,
                total_pages,
            )
            if session_key:
                set_current_view(session_key, make_page_key(file_id, next_page))
            return (
                next_page,
                total_pages,
                preview_src,
                preview_notice,
                *self.get_cached_page_outputs(
                    page_outputs_cache,
                    next_page,
                    file_id,
                    session_key=session_key,
                ),
            )
        finally:
            self._page_change_lock[lock_key] = False

    def on_prev_page(
        self,
        current_page,
        file_id,
        file_path,
        page_outputs_cache,
        total_pages,
        request: gr.Request = _DIRECT_CALL_REQUEST,
    ):
        return self.on_page_change(
            current_page,
            -1,
            file_id,
            file_path,
            page_outputs_cache,
            total_pages,
            request=request,
        )

    def on_next_page(
        self,
        current_page,
        file_id,
        file_path,
        page_outputs_cache,
        total_pages,
        request: gr.Request = _DIRECT_CALL_REQUEST,
    ):
        return self.on_page_change(
            current_page,
            1,
            file_id,
            file_path,
            page_outputs_cache,
            total_pages,
            request=request,
        )

    def on_page_set(
        self,
        current_page,
        file_id,
        file_path,
        page_outputs_cache,
        total_pages,
        request: gr.Request = _DIRECT_CALL_REQUEST,
    ):
        del file_path
        lock_key = file_id or "default"
        session_key = getattr(request, "session_hash", None) or "default"

        if self._page_change_lock.get(lock_key, False):
            logger.debug(f"Page set ignored for file {lock_key}, page={current_page}")
            # Return gr.skip() for all 10 outputs to match the expected output count
            return (
                gr.skip(),  # page_number
                gr.skip(),  # total_pages
                gr.skip(),  # preview_src
                gr.skip(),  # preview_notice
                gr.skip(),  # last_question
                gr.skip(),  # info_panel
                gr.skip(),  # plot_panel
                gr.skip(),  # state_plot_panel
                gr.skip(),  # answer_panel
                gr.skip(),  # chatbot
            )

        try:
            self._page_change_lock[lock_key] = True

            if not file_id:
                (
                    _,
                    total_pages,
                    preview_src,
                    preview_notice,
                ) = self._build_preview_payload(file_id, "", "", 1, 1)
                if session_key:
                    set_current_view(session_key, make_page_key(file_id, 1))
                return (
                    1,
                    total_pages,
                    preview_src,
                    preview_notice,
                    *self.get_cached_page_outputs(
                        page_outputs_cache,
                        1,
                        file_id,
                        session_key=session_key,
                    ),
                )

            file_name, file_path = self._resolve_callback_source(file_id, request)
            (
                next_page,
                total_pages,
                preview_src,
                preview_notice,
            ) = self._build_preview_payload(
                file_id,
                file_name,
                file_path,
                current_page,
                total_pages,
            )
            if session_key:
                set_current_view(session_key, make_page_key(file_id, next_page))
            return (
                next_page,
                total_pages,
                preview_src,
                preview_notice,
                *self.get_cached_page_outputs(
                    page_outputs_cache,
                    next_page,
                    file_id,
                    session_key=session_key,
                ),
            )
        finally:
            self._page_change_lock[lock_key] = False

    def refresh_selected_file_preview(
        self,
        first_selector_choices,
        selected_file_ids,
        current_page,
        total_pages,
        request: gr.Request = _DIRECT_CALL_REQUEST,
    ):
        file_id, file_name, file_path = self.resolve_pdf_source(
            first_selector_choices,
            selected_file_ids,
            access=resolve_preview_access(self._app, request, _DIRECT_CALL_REQUEST),
        )
        next_file_id, must_force_first, target_page = self._resolve_target_page(
            file_id, current_page
        )
        (
            page_number,
            total_pages,
            preview_src,
            preview_notice,
        ) = self._build_preview_payload(
            file_id,
            file_name,
            file_path,
            target_page,
            total_pages,
        )
        self._sync_preview_tracking(next_file_id, must_force_first, page_number)
        return (
            file_id,
            file_name,
            file_path,
            page_number,
            total_pages,
            preview_src,
            preview_notice,
        )

    def on_preview_tick(
        self,
        file_id=None,
        file_name=None,
        file_path=None,
        current_page=None,
        total_pages=None,
        current_preview_src=None,
        current_preview_notice=None,
        request: gr.Request = _DIRECT_CALL_REQUEST,
    ):
        values, request = normalize_preview_tick(
            [
                file_id,
                file_name,
                file_path,
                current_page,
                total_pages,
                current_preview_src,
                current_preview_notice,
            ],
            request,
            _DIRECT_CALL_REQUEST,
        )
        (
            file_id,
            file_name,
            file_path,
            current_page,
            total_pages,
            current_preview_src,
            current_preview_notice,
        ) = values

        if not file_id:
            return gr.skip(), gr.skip(), gr.skip(), gr.skip()

        file_name, file_path = self._resolve_callback_source(str(file_id), request)

        # Skip PDF files - they don't need polling
        if file_name and file_name.lower().endswith(".pdf"):
            return gr.skip(), gr.skip(), gr.skip(), gr.skip()

        # Skip text-like files - they don't need conversion
        if file_name and file_name.lower().endswith(
            (".txt", ".md", ".html", ".htm", ".mhtml")
        ):
            return gr.skip(), gr.skip(), gr.skip(), gr.skip()

        poll_office_conversion(self, file_name, file_path)

        next_file_id, must_force_first, target_page = self._resolve_target_page(
            file_id, current_page
        )
        (
            page_number,
            next_total_pages,
            preview_src,
            preview_notice,
        ) = self._build_preview_payload(
            file_id,
            file_name,
            file_path,
            target_page,
            total_pages,
        )
        self._sync_preview_tracking(next_file_id, must_force_first, page_number)
        if (
            int(page_number or 1) == int(target_page or 1)
            and int(next_total_pages or 1) == int(total_pages or 1)
            and (preview_src or "") == (current_preview_src or "")
            and (preview_notice or "") == (current_preview_notice or "")
        ):
            return gr.skip(), gr.skip(), gr.skip(), gr.skip()
        return page_number, next_total_pages, preview_src, preview_notice

    def _resolve_target_page(self, file_id: str, current_page: int):
        next_file_id = file_id or ""
        prev_file_id = self._last_preview_file_id or ""
        must_force_first = bool(
            next_file_id and next_file_id == (self._force_first_page_file_id or "")
        )
        file_changed = bool(next_file_id and next_file_id != prev_file_id)
        target_page = 1 if (must_force_first or file_changed) else current_page
        return next_file_id, must_force_first, target_page

    def _sync_preview_tracking(
        self, next_file_id: str, must_force_first: bool, page_number: int
    ):
        if must_force_first and int(page_number or 1) == 1:
            self._force_first_page_file_id = ""
        self._last_preview_file_id = next_file_id

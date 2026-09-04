from __future__ import annotations

import hashlib
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from .errors import PreviewErrorCode, PreviewSourceError


@dataclass(frozen=True)
class PdfPage:
    path: Path
    signature: str
    page: int
    total_pages: int
    text: str


class PdfService:
    """Strict PDF access over stable file snapshots with bounded caches."""

    def __init__(self, *, max_cache_entries: int = 128) -> None:
        self._max_cache_entries = max(1, int(max_cache_entries))
        self._count_cache: OrderedDict[str, int] = OrderedDict()
        self._text_cache: OrderedDict[tuple[str, int, int], str] = OrderedDict()
        self._path_signatures: OrderedDict[Path, str] = OrderedDict()
        self._condition = threading.Condition()
        self._inflight: set[str] = set()

    def page_count(self, file_path: str | Path) -> int:
        path, file_obj, signature = self._snapshot(file_path)
        try:
            with self._condition:
                self._record_signature(path, signature)
                cached = self._cache_get(self._count_cache, signature)
                if cached is not None:
                    return cached
                self._claim(signature)
                cached = self._cache_get(self._count_cache, signature)
                if cached is not None:
                    self._release(signature)
                    return cached
            try:
                count, _text = _read_pdf(file_obj, path)
                with self._condition:
                    self._cache_put(self._count_cache, signature, count)
                return count
            finally:
                self._release(signature)
        finally:
            file_obj.close()

    def page(
        self,
        file_path: str | Path,
        page: int,
        *,
        max_chars: int = 7000,
    ) -> PdfPage:
        path, file_obj, signature = self._snapshot(file_path)
        requested_page = max(1, int(page or 1))
        text_limit = max(0, int(max_chars))
        try:
            with self._condition:
                self._record_signature(path, signature)
                cached = self._cached_page(signature, requested_page, text_limit)
                if cached is not None:
                    return _page_result(path, signature, cached)
                self._claim(signature)
                cached = self._cached_page(signature, requested_page, text_limit)
                if cached is not None:
                    self._release(signature)
                    return _page_result(path, signature, cached)
            try:
                count, extracted = _read_pdf(file_obj, path, requested_page)
                selected_page = min(requested_page, count)
                text = _normalize_text(extracted, text_limit)
                with self._condition:
                    self._cache_put(self._count_cache, signature, count)
                    self._cache_put(
                        self._text_cache,
                        (signature, selected_page, text_limit),
                        text,
                    )
                return PdfPage(path, signature, selected_page, count, text)
            finally:
                self._release(signature)
        finally:
            file_obj.close()

    def _snapshot(self, file_path: str | Path) -> tuple[Path, BinaryIO, str]:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise _pdf_error(
                PreviewErrorCode.SOURCE_MISSING,
                path,
                "Verify that the PDF exists and is a regular file.",
            )
        try:
            file_obj = path.open("rb")
            source_stat = os.fstat(file_obj.fileno())
        except FileNotFoundError as exc:
            raise _pdf_error(
                PreviewErrorCode.SOURCE_MISSING,
                path,
                "Verify that the PDF exists and is a regular file.",
            ) from exc
        except OSError as exc:
            raise _pdf_error(
                PreviewErrorCode.SOURCE_INVALID,
                path,
                f"The PDF cannot be opened: {exc}",
            ) from exc
        return path, file_obj, _snapshot_signature(path, source_stat)

    def _cached_page(
        self,
        signature: str,
        requested_page: int,
        text_limit: int,
    ) -> tuple[int, int, str] | None:
        count = self._cache_get(self._count_cache, signature)
        if count is None:
            return None
        selected_page = min(requested_page, count)
        text = self._cache_get(
            self._text_cache,
            (signature, selected_page, text_limit),
        )
        if text is None:
            return None
        return selected_page, count, text

    def _claim(self, signature: str) -> None:
        while signature in self._inflight:
            self._condition.wait()
        self._inflight.add(signature)

    def _release(self, signature: str) -> None:
        with self._condition:
            self._inflight.discard(signature)
            self._condition.notify_all()

    def _record_signature(self, path: Path, signature: str) -> None:
        previous = self._path_signatures.pop(path, None)
        if previous is not None and previous != signature:
            self._evict_signature(previous)
        self._path_signatures[path] = signature
        while len(self._path_signatures) > self._max_cache_entries:
            _old_path, old_signature = self._path_signatures.popitem(last=False)
            self._evict_signature(old_signature)

    def _evict_signature(self, signature: str) -> None:
        self._count_cache.pop(signature, None)
        for key in [key for key in self._text_cache if key[0] == signature]:
            self._text_cache.pop(key, None)

    def _cache_get(self, cache: OrderedDict[Any, Any], key: Any) -> Any:
        value = cache.get(key)
        if value is not None:
            cache.move_to_end(key)
        return value

    def _cache_put(self, cache: OrderedDict[Any, Any], key: Any, value: Any) -> None:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > self._max_cache_entries:
            cache.popitem(last=False)


def _read_pdf(
    file_obj: BinaryIO,
    path: Path,
    requested_page: int | None = None,
) -> tuple[int, str]:
    try:
        file_obj.seek(0)
        if not file_obj.read(5).startswith(b"%PDF-"):
            raise ValueError("the PDF signature is missing")
        file_obj.seek(0)
        reader = _pdf_reader_class()(file_obj, strict=False)
        count = len(reader.pages)
        if not count:
            raise ValueError("the PDF has no pages")
        if requested_page is None:
            return count, ""
        selected_page = min(requested_page, count)
        return count, reader.pages[selected_page - 1].extract_text() or ""
    except Exception as exc:
        raise _pdf_error(
            PreviewErrorCode.SOURCE_INVALID,
            path,
            f"The PDF cannot be parsed and previewed: {exc}",
        ) from exc


def _pdf_reader_class() -> Any:
    injected = globals().get("PdfReader")
    if injected is not None:
        return injected
    from pypdf import PdfReader

    return PdfReader


def _snapshot_signature(path: Path, source_stat: os.stat_result) -> str:
    raw = "|".join(
        str(value)
        for value in (
            path,
            source_stat.st_dev,
            source_stat.st_ino,
            source_stat.st_size,
            source_stat.st_mtime_ns,
            source_stat.st_ctime_ns,
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_text(text: str, max_chars: int) -> str:
    return " ".join(str(text).split())[:max_chars]


def _page_result(
    path: Path,
    signature: str,
    cached: tuple[int, int, str],
) -> PdfPage:
    selected_page, total_pages, text = cached
    return PdfPage(path, signature, selected_page, total_pages, text)


def _pdf_error(
    code: PreviewErrorCode,
    path: Path,
    details: str,
) -> PreviewSourceError:
    return PreviewSourceError(
        code,
        stage="pdf_validation",
        source_path=path,
        converter="pypdf",
        details=details,
    )

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from .errors import PreviewErrorCode, PreviewSourceError
from .source import source_signature


@dataclass(frozen=True)
class PdfPage:
    path: Path
    signature: str
    page: int
    total_pages: int
    text: str


class PdfService:
    """Strict PDF count and text access cached by immutable source metadata."""

    def __init__(self) -> None:
        self._count_cache: dict[str, int] = {}
        self._text_cache: dict[tuple[str, int, int], str] = {}
        self._path_signatures: dict[Path, str] = {}
        self._cache_lock = threading.Lock()

    def page_count(self, file_path: str | Path) -> int:
        path, signature = self._snapshot(file_path)
        return self._page_count(path, signature)

    def page(
        self,
        file_path: str | Path,
        page: int,
        *,
        max_chars: int = 7000,
    ) -> PdfPage:
        path, signature = self._snapshot(file_path)
        total_pages = self._page_count(path, signature)
        selected_page = min(max(1, int(page or 1)), total_pages)
        text_limit = max(0, int(max_chars))
        cache_key = (signature, selected_page, text_limit)
        with self._cache_lock:
            cached_text = self._text_cache.get(cache_key)
        if cached_text is None:
            reader = self._reader(path)
            extracted = reader.pages[selected_page - 1].extract_text() or ""
            cached_text = " ".join(str(extracted).split())[:text_limit]
            with self._cache_lock:
                self._text_cache[cache_key] = cached_text
        return PdfPage(
            path=path,
            signature=signature,
            page=selected_page,
            total_pages=total_pages,
            text=cached_text,
        )

    def _snapshot(self, file_path: str | Path) -> tuple[Path, str]:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise _pdf_error(
                PreviewErrorCode.SOURCE_MISSING,
                path,
                "Verify that the PDF exists and is a regular file.",
            )
        signature = source_signature(path)
        with self._cache_lock:
            previous = self._path_signatures.get(path)
            if previous is not None and previous != signature:
                self._count_cache.pop(previous, None)
                stale_keys = [key for key in self._text_cache if key[0] == previous]
                for key in stale_keys:
                    self._text_cache.pop(key, None)
            self._path_signatures[path] = signature
        return path, signature

    def _page_count(self, path: Path, signature: str) -> int:
        with self._cache_lock:
            cached_count = self._count_cache.get(signature)
        if cached_count is not None:
            return cached_count
        count = len(self._reader(path).pages)
        with self._cache_lock:
            self._count_cache[signature] = count
        return count

    @staticmethod
    def _reader(path: Path) -> PdfReader:
        try:
            with path.open("rb") as file_obj:
                if not file_obj.read(5).startswith(b"%PDF-"):
                    raise ValueError("the PDF signature is missing")
            reader = PdfReader(str(path), strict=False)
            if not reader.pages:
                raise ValueError("the PDF has no pages")
            return reader
        except Exception as exc:
            raise _pdf_error(
                PreviewErrorCode.SOURCE_INVALID,
                path,
                f"The PDF cannot be parsed and previewed: {exc}",
            ) from exc


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

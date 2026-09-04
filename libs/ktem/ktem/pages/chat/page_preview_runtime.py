"""Runtime utilities for PDF preview and file management.

Provides helper functions for PDF handling, file signatures, and preview directory management.
"""

import hashlib
import os
import re
import shutil
import tempfile
from html import escape
from pathlib import Path
from urllib.parse import quote

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from ...assets import get_pdfjs_runtime_dir
from ...utils.render import BASE_PATH
from .page_preview_types import is_pdf_source


def get_file_signature(file_path: str) -> str:
    """Generate a unique signature for a file based on path, size, and modification time.

    Args:
        file_path: Path to the file

    Returns:
        MD5 hash of the file metadata
    """
    try:
        stat = os.stat(file_path)
        raw = f"{os.path.abspath(file_path)}|{stat.st_size}|{int(stat.st_mtime_ns)}"
    except OSError:
        raw = os.path.abspath(file_path)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def build_pdfjs_viewer_src(file_path: str, page: int, fit_mode: str = "pdf") -> str:
    """Build PDF.js viewer URL with query parameters for page and fit mode.

    Args:
        file_path: Path to the PDF file
        page: Page number to display (1-indexed)
        fit_mode: Fit mode for PDF.js ('pdf', 'width', 'height', etc.)

    Returns:
        Complete URL for PDF.js viewer or empty string if viewer not found
    """
    from theflow.settings import settings as flowsettings

    pdfjs_dir = get_pdfjs_runtime_dir(getattr(flowsettings, "KH_APP_DATA_DIR", None))
    viewer_html_path = pdfjs_dir / "web" / "viewer.html"
    if not viewer_html_path.is_file():
        return ""

    normalized_viewer_path = str(viewer_html_path).replace("\\", "/")
    normalized_pdf_path = file_path.replace("\\", "/")
    pdf_src = f"{BASE_PATH}/file={normalized_pdf_path}"
    encoded_pdf_src = quote(pdf_src, safe="")
    page_num = max(1, int(page or 1))
    query = (
        f"embed=1&disablehistory=true&sidebarviewonload=0"
        f"&ktempage={page_num}&ktemv=12&ktemfit={quote(fit_mode or 'pdf', safe='')}"
        f"&file={encoded_pdf_src}"
    )
    return f"{BASE_PATH}/file={normalized_viewer_path}?{query}#page={page_num}"


def notice_html(message: str) -> str:
    """Generate HTML for displaying a notice message.

    Args:
        message: Notice text to display

    Returns:
        HTML string with notice styling
    """
    return f"<div class='pdf-preview-notice'>{escape(str(message or ''), quote=True)}</div>"


def safe_int(value, fallback: int = 1) -> int:
    """Safely convert a value to integer with fallback.

    Args:
        value: Value to convert
        fallback: Default value if conversion fails

    Returns:
        Converted integer or fallback
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def clamp_page(page: int, total_pages: int) -> int:
    """Clamp page number to valid range [1, total_pages].

    Args:
        page: Requested page number
        total_pages: Total number of pages in the document

    Returns:
        Clamped page number within valid range
    """
    if total_pages < 1:
        total_pages = 1
    return min(max(1, int(page or 1)), int(total_pages))


def safe_pdf_page_count(pdf_path: str, fallback: int = 1, logger=None) -> int:
    """Safely get the number of pages in a PDF file.

    Args:
        pdf_path: Path to the PDF file
        fallback: Default page count if reading fails
        logger: Optional logger for error messages

    Returns:
        Number of pages in the PDF or fallback value
    """
    fallback = max(1, safe_int(fallback, 1))
    if not pdf_path or not os.path.isfile(pdf_path):
        return fallback
    try:
        return max(1, len(PdfReader(pdf_path, strict=False).pages))
    except (OSError, PdfReadError, ValueError) as exc:
        if logger is not None:
            logger.warning("Failed to read PDF total pages from %s: %s", pdf_path, exc)
        return fallback


def is_valid_pdf(pdf_path: str) -> bool:
    """Check if a file is a valid PDF with at least one page.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        True if valid PDF, False otherwise
    """
    try:
        if not pdf_path or (not os.path.isfile(pdf_path)):
            return False
        if os.path.getsize(pdf_path) < 64:
            return False
        pages = len(PdfReader(pdf_path, strict=False).pages)
        return pages > 0
    except (OSError, PdfReadError, ValueError):
        return False


def get_pdf_preview_dir() -> str:
    """Get or create the temporary directory for PDF previews.

    Returns:
        Path to the PDF preview directory
    """
    gradio_temp_dir = os.environ.get("GRADIO_TEMP_DIR", tempfile.gettempdir())
    preview_dir = os.path.join(gradio_temp_dir, "pdf_previews")
    os.makedirs(preview_dir, exist_ok=True)
    return preview_dir


def ensure_pdf_preview_copy(file_path: str, file_name: str) -> str:
    """Ensure a copy of the PDF exists in the preview directory.

    Creates a copy of the source PDF in the Gradio temp directory for safe access.

    Args:
        file_path: Path to the source PDF file
        file_name: Name of the file (used to check if it's a PDF)

    Returns:
        Path to the preview copy or original path if not a PDF
    """
    if not file_path or not os.path.isfile(file_path):
        return ""
    if not is_pdf_source(file_name, file_path):
        return file_path

    preview_dir = Path(get_pdf_preview_dir())
    source = Path(file_path).resolve()
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source.stem).strip("._")
    safe_stem = safe_stem[:80] or "preview"
    signature = get_file_signature(str(source))[:16]
    preview_path = preview_dir / f"{safe_stem}_{signature}.pdf"
    if preview_path.is_file() and preview_path.stat().st_size == source.stat().st_size:
        return str(preview_path)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=preview_dir,
            prefix=f".{safe_stem}-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
        shutil.copyfile(source, temp_path)
        os.replace(temp_path, preview_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    return str(preview_path)

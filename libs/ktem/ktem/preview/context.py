from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .errors import PreviewError


class PreviewPurpose(str, Enum):
    WEB = "web"
    DOCQA = "docqa"
    INDEXING = "indexing"
    ACCEPTANCE = "acceptance"


@dataclass(frozen=True)
class PageContext:
    source_path: Path
    file_name: str
    purpose: PreviewPurpose
    page: int
    total_pages: int
    text: str
    pdf_path: Path | None
    used_text_fallback: bool = False
    diagnostic: PreviewError | None = None

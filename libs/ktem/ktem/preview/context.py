from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .errors import PreviewError


class PreviewPurpose(str, Enum):
    WEB = "web"
    DOCQA = "docqa"
    INDEXING = "indexing"
    ACCEPTANCE = "acceptance"


@dataclass(frozen=True)
class PreviewAccess:
    user_id: str
    owner_required: bool = False


def preview_access_for_user(app: Any, user_id: Any = None) -> PreviewAccess:
    owner_required = bool(getattr(app, "f_user_management", False))
    principal = (
        user_id if user_id is not None else ("" if owner_required else "default")
    )
    return PreviewAccess(user_id=str(principal or ""), owner_required=owner_required)


@dataclass(frozen=True)
class ResolvedPreviewSource:
    file_id: str
    name: str
    path: Path
    owner: str
    index_id: int | str
    stored_path: str = ""
    size: int = 0
    date_created: Any = None


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
    source: ResolvedPreviewSource | None = None

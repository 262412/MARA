from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class PreviewSourceKind(str, Enum):
    PDF = "pdf"
    OOXML = "ooxml"
    CFB = "cfb"


@dataclass(frozen=True)
class ArchiveLimits:
    max_entries: int = 10_000
    max_uncompressed_bytes: int = 512 * 1024 * 1024
    max_compression_ratio: float = 1_000.0


@dataclass(frozen=True)
class PreviewSource:
    path: Path
    cache_path: Path
    kind: PreviewSourceKind
    extension: str
    signature: str


@dataclass(frozen=True)
class ConversionAttempt:
    converter: str
    code: str
    stage: str
    details: str

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from pathlib import Path

from .models import ConversionAttempt


class PreviewErrorCode(str, Enum):
    SOURCE_MISSING = "source_missing"
    SOURCE_TYPE_MISMATCH = "source_type_mismatch"
    SOURCE_ARCHIVE_INVALID = "source_archive_invalid"
    SOURCE_INVALID = "source_invalid"
    CONVERTER_UNAVAILABLE = "converter_unavailable"
    CONVERTER_TIMEOUT = "converter_timeout"
    CONVERTER_FAILED = "converter_failed"
    OUTPUT_MISSING = "output_missing"
    OUTPUT_INVALID = "output_invalid"
    CLEANUP_FAILED = "cleanup_failed"


class PreviewError(RuntimeError):
    """Actionable preview failure with stable machine-readable context."""

    def __init__(
        self,
        code: PreviewErrorCode,
        *,
        stage: str,
        source_path: str | Path,
        converter: str,
        details: str,
        attempts: Sequence[ConversionAttempt] = (),
    ) -> None:
        self.code = code
        self.stage = stage
        self.source_path = Path(source_path).expanduser().resolve()
        self.converter = converter
        self.details = details
        self.attempts = tuple(attempts)
        super().__init__(self._message())

    def _message(self) -> str:
        return (
            f"[{self.code.value}] stage={self.stage} "
            f"file={self.source_path} converter={self.converter}: {self.details}"
        )

    def as_attempt(self) -> ConversionAttempt:
        return ConversionAttempt(
            converter=self.converter,
            code=self.code.value,
            stage=self.stage,
            details=self.details,
        )


class PreviewSourceError(PreviewError):
    """The source is absent, corrupt, unsafe, or does not match its type."""


class PreviewConversionError(PreviewError):
    """A converter could not create a validated preview output."""


class PreviewCleanupError(PreviewError):
    """An isolated conversion workspace could not be removed."""

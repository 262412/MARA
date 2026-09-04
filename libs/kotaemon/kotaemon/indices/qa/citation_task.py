from __future__ import annotations

import threading
from typing import Any

from .citation import CitationToolCallConfigurationError


class CitationTask:
    """Carry a citation call across the answer pipeline's worker thread."""

    def __init__(self, pipeline: Any, *, context: str, question: str) -> None:
        self.pipeline = pipeline
        self.context = context
        self.question = question
        self.result: Any = None
        self.error: CitationToolCallConfigurationError | None = None

    def run(self) -> None:
        try:
            self.result = self.pipeline(context=self.context, question=self.question)
        except CitationToolCallConfigurationError as exc:
            self.error = exc

    def finish(self, thread: threading.Thread | None, timeout: float) -> Any:
        if thread is None:
            return None
        thread.join(timeout=timeout)
        if self.error is not None:
            raise self.error
        return self.result

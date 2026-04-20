"""Kotaemon - Knowledge and Text Extraction and Management."""

from .runtime_bootstrap import bootstrap_runtime_settings
from .utils.dependencies import DependencyChecker

bootstrap_runtime_settings()

__all__ = ["DependencyChecker"]

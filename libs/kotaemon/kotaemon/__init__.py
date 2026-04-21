import logging
from importlib import import_module

_LAZY_SUBMODULES = {"agents", "cli"}


def bootstrap_runtime_settings() -> str | None:
    """Best-effort bridge to the app runtime bootstrap.

    Keep this import lazy so importing ``kotaemon`` does not pull ``ktem`` into
    standalone core-library processes.
    """

    try:
        from ktem.runtime_bootstrap import (
            bootstrap_runtime_settings as _bootstrap_runtime_settings,
        )
    except ImportError:  # pragma: no cover - standalone kotaemon installs
        return None

    return _bootstrap_runtime_settings()


def __getattr__(name: str):
    if name in _LAZY_SUBMODULES:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


logger = logging.getLogger(__name__)
try:
    import posthog

    def capture(*args, **kwargs):
        logger.info("posthog.capture called with args: %s, kwargs: %s", args, kwargs)

    posthog.capture = capture
except ImportError:
    pass

try:
    import os

    os.environ["HAYSTACK_TELEMETRY_ENABLED"] = "False"
    import haystack.telemetry

    haystack.telemetry.telemetry = None
except ImportError:
    pass

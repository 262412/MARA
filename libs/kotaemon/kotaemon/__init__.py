import logging
from typing import Callable

bootstrap_runtime_settings: Callable[[], str] | None
try:
    from ktem.runtime_bootstrap import bootstrap_runtime_settings
except ImportError:  # pragma: no cover - standalone kotaemon installs
    bootstrap_runtime_settings = None
else:
    if bootstrap_runtime_settings is not None:
        bootstrap_runtime_settings()

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

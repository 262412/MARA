from __future__ import annotations

from time import monotonic
from typing import Any

DEFAULT_OPTIONAL_STAGE_RESERVE_SECONDS = 12.0


def remaining_route_seconds(request: Any) -> float | None:
    deadline = getattr(request, "route_deadline_monotonic", None)
    if deadline is None or deadline == "":
        return None
    return max(0.0, float(deadline) - monotonic())


def optional_stage_allowed(
    request: Any,
    *,
    reserve_seconds: float = DEFAULT_OPTIONAL_STAGE_RESERVE_SECONDS,
) -> bool:
    remaining = remaining_route_seconds(request)
    return remaining is None or remaining > reserve_seconds


def route_budget_metadata(request: Any) -> dict[str, Any]:
    remaining = remaining_route_seconds(request)
    return {
        "route_timeout_seconds": getattr(request, "route_timeout_seconds", None),
        "remaining_route_seconds": (
            round(remaining, 4) if remaining is not None else None
        ),
    }

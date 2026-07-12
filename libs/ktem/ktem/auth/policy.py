"""Canonical authentication configuration policy."""

from __future__ import annotations

import ipaddress
import warnings
from typing import Any

AUTH_MODES = ("auto", "local", "password", "sso")
LOCAL_AUTH_MODES = frozenset({"auto", "local"})

NO_MANAGED_USER_DIAGNOSTIC = (
    "No managed default user is available. Create an existing admin user or set "
    "both KH_FEATURE_USER_MANAGEMENT_ADMIN and "
    "KH_FEATURE_USER_MANAGEMENT_PASSWORD to nonempty secure values; admin/admin "
    "is rejected."
)


class AuthConfigurationError(ValueError):
    """Raised when authentication settings would expose MARA unsafely."""


def _is_loopback_host(host: str | None) -> bool:
    if host is None or not str(host).strip():
        return True

    normalized_host = str(host).strip()
    if normalized_host.casefold().rstrip(".") == "localhost":
        return True
    if normalized_host.startswith("[") and normalized_host.endswith("]"):
        normalized_host = normalized_host[1:-1]

    try:
        return ipaddress.ip_address(normalized_host).is_loopback
    except ValueError:
        return False


def resolve_auth_mode(
    *,
    configured_mode: str | None = None,
    host: str | None = None,
    legacy_sso_enabled: bool | None = None,
) -> str:
    """Resolve canonical auth configuration and enforce loopback-only modes."""
    if configured_mode is None:
        if legacy_sso_enabled is True:
            warnings.warn(
                "KH_SSO_ENABLED is deprecated; set MARA_AUTH_MODE=sso. This "
                "compatibility mapping will be removed after one minor release.",
                DeprecationWarning,
                stacklevel=2,
            )
            mode = "sso"
        else:
            mode = "auto"
    else:
        mode = str(configured_mode).strip()

    if mode not in AUTH_MODES:
        allowed = ", ".join(AUTH_MODES)
        raise AuthConfigurationError(
            f"Invalid MARA_AUTH_MODE={mode!r}. Expected one of: {allowed}."
        )

    if mode in LOCAL_AUTH_MODES and not _is_loopback_host(host):
        raise AuthConfigurationError(
            f"MARA_AUTH_MODE={mode!r} cannot bind to non-loopback host {host!r}. "
            "Set MARA_AUTH_MODE=password or MARA_AUTH_MODE=sso before exposing "
            "MARA on a network."
        )

    return mode


def resolve_legacy_bootstrap_credentials(
    settings: Any,
) -> tuple[str, str] | None:
    """Resolve one-release legacy admin bootstrap credentials."""
    username = str(
        getattr(settings, "KH_FEATURE_USER_MANAGEMENT_ADMIN", "") or ""
    ).strip()
    password = str(getattr(settings, "KH_FEATURE_USER_MANAGEMENT_PASSWORD", "") or "")

    if not username and not password:
        return None

    warnings.warn(
        "KH_FEATURE_USER_MANAGEMENT_ADMIN and "
        "KH_FEATURE_USER_MANAGEMENT_PASSWORD bootstrap is deprecated and will be "
        "removed after one minor release.",
        DeprecationWarning,
        stacklevel=2,
    )

    if not username or not password.strip():
        raise AuthConfigurationError(
            "Legacy bootstrap requires both KH_FEATURE_USER_MANAGEMENT_ADMIN and "
            "KH_FEATURE_USER_MANAGEMENT_PASSWORD to be nonempty."
        )
    if username == "admin" and password == "admin":
        raise AuthConfigurationError(
            "Legacy admin/admin bootstrap credentials are rejected. Configure a "
            "non-default admin username and strong password."
        )

    return username, password

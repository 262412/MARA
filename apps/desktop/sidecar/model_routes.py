from __future__ import annotations

import os
from typing import Any


def prepare_model_routes() -> Any | None:
    if os.environ.get("MARA_DESKTOP_MODEL_SETTINGS") != "1":
        return None
    from ktem.desktop_model_routes import prepare_desktop_model_routes
    from ktem.embeddings.db import engine as embedding_engine
    from ktem.llms.db import engine as llm_engine
    from theflow.settings import settings as flowsettings

    if embedding_engine is not llm_engine:
        raise RuntimeError("Desktop model tables do not share one database engine.")
    llm_engine.dispose()
    return prepare_desktop_model_routes(flowsettings)


def apply_route_identity(
    payload: dict[str, Any], identity: Any | None
) -> dict[str, Any]:
    payload.update(route_diagnostics(identity))
    if identity is not None:
        payload.update(
            llm_default=identity.query_route_name,
            embedding_default=identity.embedding_route_name,
            query_provider=identity.query_provider,
            query_model=identity.query_model,
            embedding_provider=identity.embedding_provider,
            embedding_model=identity.embedding_model,
        )
    return payload


def query_route_diagnostics(
    identity: Any | None,
    readiness: Any | None,
) -> dict[str, Any]:
    diagnostics = route_diagnostics(identity)
    diagnostics.update(
        route_provider=(
            identity.query_provider
            if identity is not None
            else readiness.query_provider
            if readiness is not None
            else ""
        ),
        route_model=(
            identity.query_model
            if identity is not None
            else readiness.query_model
            if readiness is not None
            else ""
        ),
    )
    return diagnostics


def query_route_name(identity: Any | None) -> str | None:
    return identity.query_route_name if identity is not None else None


def route_diagnostics(identity: Any | None) -> dict[str, Any]:
    if identity is None:
        return {
            "settings_revision": "",
            "sidecar_pid": os.getpid(),
            "route_fingerprint": "",
        }
    return {
        "settings_revision": str(identity.settings_revision),
        "sidecar_pid": int(identity.sidecar_pid),
        "route_fingerprint": str(identity.route_fingerprint),
    }


def settings_revision() -> str | None:
    return (
        str(os.environ.get("MARA_DESKTOP_SETTINGS_REVISION", "") or "").strip() or None
    )

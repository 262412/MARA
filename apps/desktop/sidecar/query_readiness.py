from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib.util import find_spec
from typing import Any

QUERY_READINESS_MESSAGES = {
    "llm_not_configured": "Configure a chat model before asking questions.",
    "llm_credentials_missing": "Configure credentials for the selected chat model.",
    "llm_auth_failed": "The selected chat model rejected its credentials.",
    "llm_dependency_missing": "The selected chat model is not included in this MARA build.",
    "llm_unavailable": "The selected chat model is temporarily unavailable.",
    "llm_rate_limited": "The selected chat model is rate limited. Try again later.",
    "query_timeout": "MARA did not receive answer progress before the time limit.",
    "query_runtime_failed": "MARA could not complete the answer.",
}
QUERY_READINESS_ACTIONS = {
    "llm_not_configured": "configure_llm",
    "llm_credentials_missing": "configure_credentials",
    "llm_auth_failed": "configure_credentials",
    "llm_dependency_missing": "repair_installation",
    "llm_unavailable": "check_connection",
    "llm_rate_limited": "retry",
    "query_timeout": "retry",
    "query_runtime_failed": "retry",
}
QUERY_READINESS_CODES = frozenset(QUERY_READINESS_MESSAGES)
QUERY_READINESS_ACTION_VALUES = frozenset({"none", *QUERY_READINESS_ACTIONS.values()})
PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "your-key",
        "your_api_key",
        "your_key",
        "<your_openai_key>",
        "<your_openai_api_key>",
        "<your-api-key>",
    }
)
SAFE_PROVIDER_NAMES = frozenset({"openai", "azure", "ollama"})
SAFE_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9._:@/-]{1,128}$")


@dataclass(frozen=True)
class QueryFailureContract:
    code: str
    message: str
    retryable: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }


@dataclass(frozen=True)
class QueryReadiness:
    query_ready: bool
    query_issue_code: str | None
    query_message: str
    query_action: str
    query_retryable: bool
    query_provider: str
    query_model: str
    embedding_provider: str
    embedding_model: str

    @classmethod
    def ready(
        cls,
        *,
        query_provider: str,
        query_model: str,
        embedding_provider: str = "",
        embedding_model: str = "",
    ) -> "QueryReadiness":
        return cls(
            query_ready=True,
            query_issue_code=None,
            query_message="Answer generation is ready.",
            query_action="none",
            query_retryable=False,
            query_provider=_safe_provider(query_provider),
            query_model=_safe_label(query_model),
            embedding_provider=_safe_provider(embedding_provider),
            embedding_model=_safe_label(embedding_model),
        )

    @classmethod
    def blocked(
        cls,
        *,
        code: str,
        query_provider: str = "",
        query_model: str = "",
        embedding_provider: str = "",
        embedding_model: str = "",
        retryable: bool | None = None,
    ) -> "QueryReadiness":
        if code not in QUERY_READINESS_CODES:
            code = "query_runtime_failed"
        return cls(
            query_ready=False,
            query_issue_code=code,
            query_message=QUERY_READINESS_MESSAGES[code],
            query_action=QUERY_READINESS_ACTIONS[code],
            query_retryable=(
                (code in {"llm_unavailable", "llm_rate_limited"})
                if retryable is None
                else retryable
            ),
            query_provider=_safe_provider(query_provider),
            query_model=_safe_label(query_model),
            embedding_provider=_safe_provider(embedding_provider),
            embedding_model=_safe_label(embedding_model),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "query_ready": self.query_ready,
            "query_issue_code": self.query_issue_code,
            "query_message": self.query_message,
            "query_action": self.query_action,
            "query_retryable": self.query_retryable,
            "query_provider": self.query_provider,
            "query_model": self.query_model,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
        }


def evaluate_query_readiness(
    settings: Mapping[str, Any] | None,
    *,
    desktop: bool,
    module_available: Callable[[str], bool] | None = None,
) -> QueryReadiness:
    """Evaluate the selected chat model without loading or calling a provider."""
    config = settings if isinstance(settings, Mapping) else {}
    llm_configs = _model_configs(config.get("KH_LLMS"))
    embedding_configs = _model_configs(config.get("KH_EMBEDDINGS"))
    embedding = _selected_model(embedding_configs)
    embedding_provider, embedding_spec = _model_identity(embedding)
    embedding_model = _model_name(embedding_spec)

    if not desktop:
        selected = _selected_model(llm_configs)
        provider, spec = _model_identity(selected)
        model = _model_name(spec)
        if selected is None:
            return QueryReadiness.blocked(
                code="llm_not_configured",
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
            )
        return _evaluate_selected_model(
            provider,
            spec,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            module_available=module_available,
            query_model=model,
        )

    selected = _selected_model(llm_configs)
    if selected is None:
        return QueryReadiness.blocked(
            code="llm_not_configured",
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
        )
    provider, spec = _model_identity(selected)
    return _evaluate_selected_model(
        provider,
        spec,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        module_available=module_available,
        query_model=_model_name(spec),
    )


def collect_query_readiness() -> QueryReadiness | None:
    """Read packaged settings only for Desktop; Web/CLI keep their old doctor."""
    if not str(os.environ.get("MARA_DESKTOP_DATA_DIR", "") or "").strip():
        return None
    try:
        from ktem import default_flowsettings
    except (ImportError, ModuleNotFoundError):
        return QueryReadiness.blocked(code="llm_dependency_missing")
    return evaluate_query_readiness(
        {
            "KH_LLMS": getattr(default_flowsettings, "KH_LLMS", {}),
            "KH_EMBEDDINGS": getattr(default_flowsettings, "KH_EMBEDDINGS", {}),
        },
        desktop=True,
        module_available=_module_available,
    )


def _module_available(name: str) -> bool:
    try:
        return find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def classify_query_failure(error: BaseException | str) -> QueryFailureContract:
    """Map provider/runtime failures to path-free, stable Desktop contracts."""
    code = _known_failure_code(error)
    if code is not None:
        return _failure(code)

    text = str(error).casefold()
    status_code = _status_code(error)
    if (
        isinstance(error, (ModuleNotFoundError, ImportError))
        or "no module named" in text
    ):
        return _failure("llm_dependency_missing")
    if any(
        marker in text
        for marker in ("model not found", "unknown model", "unsupported model")
    ):
        return _failure("llm_dependency_missing")
    if status_code == 429 or _contains_status(text, 429) or _rate_limited(text):
        return _failure("llm_rate_limited")
    if (
        status_code in {401, 403}
        or _contains_status(text, 401, 403)
        or any(
            marker in text
            for marker in (
                "unauthorized",
                "forbidden",
                "invalid api key",
                "authentication failed",
            )
        )
    ):
        return _failure("llm_auth_failed")
    if _credentials_missing(text):
        return _failure("llm_credentials_missing")
    if status_code in {408, 425, 500, 502, 503, 504} or _unavailable(error, text):
        return _failure("llm_unavailable")
    return _failure("query_runtime_failed")


def _evaluate_selected_model(
    provider: str,
    spec: Mapping[str, Any],
    *,
    embedding_provider: str,
    embedding_model: str,
    module_available: Callable[[str], bool] | None,
    query_model: str,
) -> QueryReadiness:
    safe_provider = _safe_provider(provider)
    if safe_provider not in SAFE_PROVIDER_NAMES:
        return QueryReadiness.blocked(
            code="llm_dependency_missing",
            query_provider=safe_provider,
            query_model=query_model,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
        )
    if module_available is not None and not module_available(
        _module_name(safe_provider)
    ):
        return QueryReadiness.blocked(
            code="llm_dependency_missing",
            query_provider=safe_provider,
            query_model=query_model,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
        )
    if not query_model:
        return QueryReadiness.blocked(
            code="llm_not_configured",
            query_provider=safe_provider,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
        )
    if safe_provider == "ollama":
        return QueryReadiness.ready(
            query_provider=safe_provider,
            query_model=query_model,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
        )
    if _missing_credentials(spec):
        return QueryReadiness.blocked(
            code="llm_credentials_missing",
            query_provider=safe_provider,
            query_model=query_model,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
        )
    if safe_provider == "azure" and not _nonempty(spec.get("azure_endpoint")):
        return QueryReadiness.blocked(
            code="llm_credentials_missing",
            query_provider=safe_provider,
            query_model=query_model,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
        )
    return QueryReadiness.ready(
        query_provider=safe_provider,
        query_model=query_model,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
    )


def _failure(code: str) -> QueryFailureContract:
    retryable = code in {"llm_unavailable", "llm_rate_limited", "query_timeout"}
    return QueryFailureContract(
        code=code,
        message=QUERY_READINESS_MESSAGES[code],
        retryable=retryable,
    )


def _known_failure_code(error: BaseException | str) -> str | None:
    code = getattr(error, "code", None)
    return str(code) if code in QUERY_READINESS_CODES else None


def _status_code(error: BaseException | str) -> int | None:
    for name in ("status_code", "status", "http_status"):
        value = getattr(error, name, None)
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    for name in ("code",):
        value = getattr(error, name, None)
        try:
            if value is not None and str(value).isdigit():
                return int(value)
        except (TypeError, ValueError):
            continue
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _contains_status(text: str, *codes: int) -> bool:
    return any(re.search(rf"(?<!\d){code}(?!\d)", text) for code in codes)


def _rate_limited(text: str) -> bool:
    return any(marker in text for marker in ("rate limit", "too many requests"))


def _credentials_missing(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "api key is missing",
            "missing api key",
            "credentials missing",
            "not configured",
            "no api key",
            "api key",
            "credential",
        )
    )


def _unavailable(error: BaseException | str, text: str) -> bool:
    if isinstance(error, (ConnectionError, TimeoutError, OSError)):
        return True
    return any(
        marker in text
        for marker in (
            "connection refused",
            "connection reset",
            "connection error",
            "temporarily unavailable",
            "timed out",
            "timeout",
            "service unavailable",
        )
    )


def _model_configs(value: Any) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(name): config
        for name, config in value.items()
        if isinstance(config, Mapping) and isinstance(config.get("spec"), Mapping)
    }


def _selected_model(
    configs: Mapping[str, Mapping[str, Any]],
) -> tuple[str, Mapping[str, Any]] | None:
    defaults = [
        (name, config)
        for name, config in configs.items()
        if bool(config.get("default"))
    ]
    if len(defaults) == 1:
        return defaults[0]
    return None


def _model_identity(
    selected: tuple[str, Mapping[str, Any]] | None,
) -> tuple[str, Mapping[str, Any]]:
    if selected is None:
        return "", {}
    name, config = selected
    spec = config.get("spec")
    if not isinstance(spec, Mapping):
        return _safe_provider(name), {}
    return _safe_provider(name) or _provider_from_type(spec.get("__type__")), spec


def _provider_from_type(value: Any) -> str:
    text = str(value or "").casefold()
    if "azure" in text:
        return "azure"
    if "ollama" in text or "local" in text:
        return "ollama"
    if "openai" in text:
        return "openai"
    return ""


def _model_name(spec: Mapping[str, Any]) -> str:
    for key in ("model", "model_name", "azure_deployment"):
        value = _safe_label(spec.get(key))
        if value:
            return value
    return ""


def _missing_credentials(spec: Mapping[str, Any]) -> bool:
    return _is_placeholder(spec.get("api_key"))


def _module_name(provider: str) -> str:
    return {"openai": "openai", "azure": "openai", "ollama": "openai"}.get(
        provider, provider
    )


def _is_placeholder(value: Any) -> bool:
    return str(value or "").strip().casefold() in PLACEHOLDER_VALUES


def _nonempty(value: Any) -> bool:
    return bool(str(value or "").strip())


def _safe_provider(value: Any) -> str:
    candidate = str(value or "").strip().casefold()
    if candidate in SAFE_PROVIDER_NAMES:
        return candidate
    return _provider_from_type(candidate)


def _safe_label(value: Any) -> str:
    candidate = str(value or "").strip()
    if (
        not candidate
        or "://" in candidate
        or candidate.startswith(("/", "\\"))
        or "\x00" in candidate
        or not SAFE_LABEL_PATTERN.fullmatch(candidate)
    ):
        return ""
    return candidate


__all__ = [
    "QueryFailureContract",
    "QueryReadiness",
    "QUERY_READINESS_ACTION_VALUES",
    "QUERY_READINESS_CODES",
    "classify_query_failure",
    "collect_query_readiness",
    "evaluate_query_readiness",
]

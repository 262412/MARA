from __future__ import annotations

import errno
import importlib.util
import logging
import os
import re
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import OperationalError as SqlAlchemyOperationalError

LOGGER = logging.getLogger("mara.desktop.index_tasks")

PLACEHOLDER_CREDENTIALS = {
    "",
    "<your_openai_key>",
    "your-key",
    "your_api_key",
    "your_key",
}
SUPPORTED_EMBEDDING_TYPES = {
    "kotaemon.embeddings.AzureOpenAIEmbeddings": "openai",
    "kotaemon.embeddings.OpenAIEmbeddings": "openai",
}
INDEXING_MESSAGES = {
    "embedding_not_configured": (
        "Configure a supported embedding model before indexing files."
    ),
    "embedding_dependency_missing": (
        "The configured embedding provider is not included in this MARA Desktop build."
    ),
    "embedding_unavailable": (
        "The configured embedding provider is temporarily unavailable."
    ),
    "index_runtime_storage_unwritable": (
        "MARA Desktop cannot write its indexing cache or state."
    ),
    "source_permission_denied": "MARA Desktop cannot read the selected source file.",
    "source_not_found": "The selected source file no longer exists.",
    "index_database_locked": "MARA data is temporarily busy.",
    "index_storage_full": "MARA does not have enough free storage to index this file.",
    "index_failed": "MARA could not index this file.",
}
INDEXING_ACTIONS = {
    "embedding_not_configured": "configure_embedding",
    "embedding_dependency_missing": "repair_installation",
    "embedding_unavailable": "check_connection",
    "index_runtime_storage_unwritable": "contact_support",
    "source_permission_denied": "check_source_permissions",
    "source_not_found": "choose_source_again",
    "index_database_locked": "retry",
    "index_storage_full": "free_storage",
    "index_failed": "retry",
}
RETRYABLE_CODES = {
    "embedding_unavailable",
    "index_database_locked",
    "index_failed",
    "index_storage_full",
}


@dataclass(frozen=True)
class IndexingReadiness:
    indexing_ready: bool
    indexing_issue_code: str | None
    indexing_message: str
    indexing_action: str
    retryable: bool

    @classmethod
    def ready(cls) -> "IndexingReadiness":
        return cls(True, None, "File indexing is ready.", "none", False)

    @classmethod
    def blocked(
        cls,
        *,
        code: str,
        message: str | None = None,
        action: str | None = None,
        retryable: bool | None = None,
    ) -> "IndexingReadiness":
        return cls(
            False,
            code,
            message or INDEXING_MESSAGES[code],
            action or INDEXING_ACTIONS[code],
            code in RETRYABLE_CODES if retryable is None else retryable,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "indexing_ready": self.indexing_ready,
            "indexing_issue_code": self.indexing_issue_code,
            "indexing_message": self.indexing_message,
            "indexing_action": self.indexing_action,
            "indexing_retryable": self.retryable,
        }


@dataclass(frozen=True)
class IndexFailureContract:
    code: str
    message: str
    retryable: bool


class DesktopIndexingPreflightError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        status_code: int,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code

    @classmethod
    def from_readiness(
        cls,
        readiness: IndexingReadiness,
    ) -> "DesktopIndexingPreflightError":
        if readiness.indexing_ready or readiness.indexing_issue_code is None:
            raise ValueError("Ready indexing state cannot become an error")
        return cls(
            readiness.indexing_issue_code,
            readiness.indexing_message,
            retryable=readiness.retryable,
            status_code=_status_for_code(readiness.indexing_issue_code),
        )


def evaluate_embedding_readiness(
    configurations: Mapping[str, Any],
    *,
    module_available: Callable[[str], bool] = lambda module: (
        importlib.util.find_spec(module) is not None
    ),
) -> IndexingReadiness:
    defaults = [
        config
        for config in configurations.values()
        if isinstance(config, Mapping) and bool(config.get("default"))
    ]
    if len(defaults) != 1:
        return IndexingReadiness.blocked(code="embedding_not_configured")

    spec = defaults[0].get("spec")
    if not isinstance(spec, Mapping):
        return IndexingReadiness.blocked(code="embedding_not_configured")
    if _has_placeholder_credentials(spec):
        return IndexingReadiness.blocked(code="embedding_not_configured")

    provider_type = str(spec.get("__type__") or "")
    dependency = SUPPORTED_EMBEDDING_TYPES.get(provider_type)
    if dependency is None or not module_available(dependency):
        return IndexingReadiness.blocked(code="embedding_dependency_missing")
    if not _supported_spec_is_configured(provider_type, spec):
        return IndexingReadiness.blocked(code="embedding_not_configured")
    return IndexingReadiness.ready()


def collect_indexing_readiness() -> IndexingReadiness:
    data_root = Path(os.environ.get("MARA_DESKTOP_DATA_DIR", ""))
    try:
        validate_indexing_storage(data_root)
        configurations = _desktop_embedding_configurations()
        return evaluate_embedding_readiness(configurations)
    except DesktopIndexingPreflightError as error:
        return IndexingReadiness.blocked(
            code=error.code,
            message=error.message,
            retryable=error.retryable,
        )
    except ModuleNotFoundError:
        return IndexingReadiness.blocked(code="embedding_dependency_missing")
    except (ConnectionError, TimeoutError):
        return IndexingReadiness.blocked(code="embedding_unavailable")
    except PermissionError:
        return IndexingReadiness.blocked(code="index_runtime_storage_unwritable")
    except Exception as error:
        LOGGER.error(
            "Indexing readiness failed error_type=%s",
            type(error).__name__,
        )
        failure = classify_index_failure(error)
        return IndexingReadiness.blocked(
            code=failure.code,
            message=failure.message,
            retryable=failure.retryable,
        )


def validate_indexing_storage(
    data_root: Path,
    *,
    probe: Callable[[Path], None] | None = None,
) -> None:
    if not data_root or not data_root.is_absolute():
        raise _preflight_error("index_runtime_storage_unwritable")
    resolved_root = data_root.expanduser().resolve()
    probe_directory = probe or _probe_writable_directory
    for directory in (resolved_root / "cache" / "theflow", resolved_root / "state"):
        if not directory.is_relative_to(resolved_root):
            raise _preflight_error("index_runtime_storage_unwritable")
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe_directory(directory)
        except OSError as error:
            if _storage_full(error):
                raise _preflight_error("index_storage_full") from None
            raise _preflight_error("index_runtime_storage_unwritable") from None


def validate_index_sources(
    paths: list[str],
    *,
    probe: Callable[[Path], None] | None = None,
) -> None:
    probe_source = probe or _probe_readable_source
    for raw_path in paths:
        source = Path(raw_path)
        if not source.exists() or not source.is_file():
            raise _preflight_error("source_not_found")
        try:
            probe_source(source)
        except PermissionError:
            raise _preflight_error("source_permission_denied") from None
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EPERM}:
                raise _preflight_error("source_permission_denied") from None
            raise _preflight_error("source_not_found") from None


def classify_index_failure(error: Exception | str) -> IndexFailureContract:
    text = str(error).casefold()
    status_code = _error_status_code(error)
    if isinstance(error, ModuleNotFoundError) or "no module named" in text:
        return _failure("embedding_dependency_missing")
    if status_code in {401, 403} or _contains_status(text, {401, 403}):
        return _failure("embedding_not_configured")
    if isinstance(error, PermissionError):
        return _failure("source_permission_denied")
    if _storage_full(error):
        return _failure("index_storage_full")
    if (
        isinstance(error, (sqlite3.OperationalError, SqlAlchemyOperationalError))
        or "database" in text
    ) and ("locked" in text or "busy" in text):
        return _failure("index_database_locked")
    if status_code in {429, 502, 503, 504} or _contains_status(
        text,
        {429, 502, 503, 504},
    ):
        return _failure("embedding_unavailable")
    if isinstance(error, (ConnectionError, TimeoutError)) or any(
        marker in text
        for marker in ("connection error", "connection refused", "timed out", "timeout")
    ):
        return _failure("embedding_unavailable")
    if "permission denied" in text:
        return _failure("index_runtime_storage_unwritable")
    if "no models in pool" in text or "api key" in text and "invalid" in text:
        return _failure("embedding_not_configured")
    return _failure("index_failed")


def _desktop_embedding_configurations() -> Mapping[str, Any]:
    from theflow.settings import settings as flowsettings

    configured = getattr(flowsettings, "KH_EMBEDDINGS", {})
    configured_readiness = evaluate_embedding_readiness(configured)
    if not configured_readiness.indexing_ready:
        return configured if isinstance(configured, Mapping) else {}

    from ktem.embeddings.manager import embedding_models_manager

    selected = _configured_default(configured)
    if selected is not None:
        from ktem.desktop_model_routes import persisted_desktop_spec

        name, config = selected
        spec = dict(config["spec"])
        persisted_spec = persisted_desktop_spec(spec, "embedding")
        current = embedding_models_manager.info().get(name)
        if current is None:
            embedding_models_manager.add(name, spec=spec, default=True)
        elif current.get("spec") != persisted_spec or not bool(current.get("default")):
            embedding_models_manager.update(name, spec=spec, default=True)
    return configured


def _configured_default(
    configurations: Any,
) -> tuple[str, Mapping[str, Any]] | None:
    if not isinstance(configurations, Mapping):
        return None
    defaults = [
        (str(name), config)
        for name, config in configurations.items()
        if isinstance(config, Mapping) and bool(config.get("default"))
    ]
    if len(defaults) != 1:
        return None
    return defaults[0]


def _has_placeholder_credentials(spec: Mapping[str, Any]) -> bool:
    credentials = [
        str(value or "").strip().casefold()
        for key, value in spec.items()
        if "key" in str(key).casefold()
    ]
    return bool(credentials) and any(
        credential in PLACEHOLDER_CREDENTIALS for credential in credentials
    )


def _supported_spec_is_configured(
    provider_type: str,
    spec: Mapping[str, Any],
) -> bool:
    api_key = str(spec.get("api_key") or "").strip().casefold()
    if not api_key or api_key in PLACEHOLDER_CREDENTIALS:
        return False
    if provider_type.endswith("AzureOpenAIEmbeddings"):
        return all(
            str(spec.get(field) or "").strip()
            for field in ("azure_endpoint", "azure_deployment")
        )
    return bool(str(spec.get("model") or "").strip())


def _probe_writable_directory(directory: Path) -> None:
    probe_path = directory / f".indexing-write-{uuid4().hex}"
    descriptor: int | None = None
    try:
        descriptor = os.open(
            probe_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    finally:
        if descriptor is not None:
            os.close(descriptor)
        probe_path.unlink(missing_ok=True)


def _probe_readable_source(source: Path) -> None:
    with source.open("rb") as source_file:
        source_file.read(1)


def _preflight_error(code: str) -> DesktopIndexingPreflightError:
    return DesktopIndexingPreflightError(
        code,
        INDEXING_MESSAGES[code],
        retryable=code in RETRYABLE_CODES,
        status_code=_status_for_code(code),
    )


def _failure(code: str) -> IndexFailureContract:
    return IndexFailureContract(
        code,
        INDEXING_MESSAGES[code],
        code in RETRYABLE_CODES,
    )


def _status_for_code(code: str) -> int:
    return {
        "embedding_not_configured": 409,
        "embedding_dependency_missing": 503,
        "embedding_unavailable": 503,
        "index_runtime_storage_unwritable": 503,
        "source_permission_denied": 403,
        "source_not_found": 404,
        "index_database_locked": 503,
        "index_storage_full": 507,
    }.get(code, 500)


def _contains_status(text: str, statuses: set[int]) -> bool:
    return any(
        re.search(rf"(?<!\d){status}(?!\d)", text) is not None for status in statuses
    )


def _error_status_code(error: Exception | str) -> int | None:
    direct_status = getattr(error, "status_code", None)
    if isinstance(direct_status, int):
        return direct_status
    response = getattr(error, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def _storage_full(error: Exception | str) -> bool:
    text = str(error).casefold()
    return (
        isinstance(error, OSError)
        and (error.errno == errno.ENOSPC or getattr(error, "winerror", None) == 112)
    ) or any(
        marker in text
        for marker in ("no space left on device", "disk full", "winerror 112")
    )

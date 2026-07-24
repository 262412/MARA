from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .docqa_image_documents import (
    element_index_records_from_documents,
    is_image_only_document,
)
from .docqa_runtime_sources import (
    document_paths,
    has_element_index,
    has_search_index,
    normalized_path,
    unindexed_document_paths,
)
from .engine_accessors import config_value
from .schemas import BenchmarkDocument

logger = logging.getLogger(__name__)


class DocQAIndexCache:
    def __init__(
        self,
        config: Any,
        *,
        shared_prepared_file_ids: dict[tuple[Any, ...], str],
    ) -> None:
        self.config = config
        self.shared_prepared_file_ids = shared_prepared_file_ids
        self.prepared_file_ids: dict[tuple[Any, ...], str] = {}
        self.indexed_paths: set[str] = set()
        self.last_trace: dict[str, Any] = {}

    def index_documents(
        self,
        runtime: Any,
        documents: list[BenchmarkDocument],
    ) -> list[str]:
        selected_ids: list[str] = []
        missing_documents: list[BenchmarkDocument] = []
        reindex_documents: list[BenchmarkDocument] = []
        identities: list[dict[str, Any]] = []
        cache_hits = 0
        cache_misses = 0

        for document in documents:
            if is_image_only_document(document):
                continue
            cache_key, identity = self.document_identity(document)
            cached_file_id = self.prepared_file_ids.get(
                cache_key
            ) or self.shared_prepared_file_ids.get(cache_key)
            if cached_file_id:
                cache_hits += 1
                identities.append({**identity, "cache_status": "hit"})
                selected_ids.append(cached_file_id)
                self.indexed_paths.add(str(document.path))
                self.prepared_file_ids[cache_key] = cached_file_id
                continue

            cache_misses += 1
            identities.append({**identity, "cache_status": "miss"})
            file_id = self.resolve_indexed_file_id(runtime, document)
            if not file_id:
                missing_documents.append(document)
                continue
            if has_search_index(runtime, file_id) and self.element_index_ready(
                runtime,
                file_id=file_id,
                document=document,
            ):
                if file_id not in selected_ids:
                    selected_ids.append(file_id)
                self.indexed_paths.add(str(document.path))
                self.remember_prepared_file(document, file_id)
            else:
                reindex_documents.append(document)

        self._index_missing_documents(runtime, missing_documents)
        self._reindex_incomplete_documents(runtime, reindex_documents)
        for document in missing_documents + reindex_documents:
            file_id = self.resolve_indexed_file_id(runtime, document)
            if file_id and file_id not in selected_ids:
                selected_ids.append(file_id)
            if file_id:
                self.remember_prepared_file(document, file_id)

        self.last_trace = {
            "hits": cache_hits,
            "misses": cache_misses,
            "identities": identities,
        }
        return selected_ids

    def resolve_indexed_file_id(
        self,
        runtime: Any,
        document: BenchmarkDocument,
    ) -> str:
        document_path = Path(document.path)
        normalized_document_path = normalized_path(str(document_path))
        try:
            records = list(runtime.list_files())
        except Exception as exc:
            logger.debug(
                "DocQA runtime file listing failed while resolving %s: %s",
                document_path,
                exc,
            )
            records = []

        for record in records:
            record_path = str(getattr(record, "path", "") or "")
            if record_path and normalized_path(record_path) == normalized_document_path:
                return str(getattr(record, "file_id", "") or "")

        exact_name_matches = [
            record
            for record in records
            if str(getattr(record, "name", "") or "").lower()
            == document_path.name.lower()
        ]
        if len(exact_name_matches) == 1:
            return str(getattr(exact_name_matches[0], "file_id", "") or "")

        for ref in (document.document_id, document_path.name, str(document_path)):
            try:
                resolved = runtime.resolve_file_refs([ref])
            except Exception as exc:
                logger.debug(
                    "DocQA runtime reference resolution failed for %s: %s",
                    ref,
                    exc,
                )
                resolved = []
            if len(resolved) == 1:
                return str(getattr(resolved[0], "file_id", "") or "")
        return ""

    def document_identity(
        self,
        document: BenchmarkDocument,
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        path = Path(document.path)
        try:
            stat = path.stat()
            size = stat.st_size
            mtime_ns = stat.st_mtime_ns
        except OSError:
            size = None
            mtime_ns = None
        requires_element = route_requires_element(self.config)
        app_data_dir = str(
            config_value(self.config, "app_data_dir", "")
            or os.environ.get("KH_APP_DATA_DIR", "")
        )
        identity = {
            "document_id": document.document_id,
            "path": normalized_path(str(path)),
            "size": size,
            "mtime_ns": mtime_ns,
            "requires_element": requires_element,
        }
        key = (
            app_data_dir,
            identity["path"],
            size,
            mtime_ns,
            requires_element,
        )
        return key, identity

    def remember_prepared_file(
        self,
        document: BenchmarkDocument,
        file_id: str,
    ) -> None:
        cache_key, _identity = self.document_identity(document)
        self.prepared_file_ids[cache_key] = file_id
        self.shared_prepared_file_ids[cache_key] = file_id

    def element_index_ready(
        self,
        runtime: Any,
        *,
        file_id: str,
        document: BenchmarkDocument,
    ) -> bool:
        if not route_requires_element(self.config):
            return True
        if element_index_records_from_documents([document]):
            return True
        return has_element_index(runtime, file_id)

    def _index_missing_documents(
        self,
        runtime: Any,
        documents: list[BenchmarkDocument],
    ) -> None:
        paths = unindexed_document_paths(
            documents,
            indexed_paths=self.indexed_paths,
        )
        if paths:
            runtime.index_paths(paths, reindex=False)
            self.indexed_paths.update(paths)

    def _reindex_incomplete_documents(
        self,
        runtime: Any,
        documents: list[BenchmarkDocument],
    ) -> None:
        paths = document_paths(documents)
        if paths:
            runtime.index_paths(paths, reindex=True)
            self.indexed_paths.update(paths)


def route_requires_element(config: Any) -> bool:
    route_policy = str(config_value(config, "route_policy", "") or "")
    route_id = str(config_value(config, "route", "") or "")
    return route_policy.replace("-", "_") in {
        "element",
        "doc_element",
        "element_rag",
    } or route_id.replace("-", "_") in {"element", "element_rag"}

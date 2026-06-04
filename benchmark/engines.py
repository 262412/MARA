from __future__ import annotations

import re
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol, cast, runtime_checkable

from kotaemon.base import RetrievedDocument

from . import controller_fields as cf
from .engine_helpers import _parsed_indexes_cache, _performance_from_timings
from .engine_result import EngineRunResult
from .schemas import BenchmarkConfig, BenchmarkDocument
from .system import KotaemonTextRAGSystem


@runtime_checkable
class BenchmarkEngine(Protocol):
    name: str

    def run(
        self,
        *,
        example: Any,
        documents: list[Any],
    ) -> EngineRunResult:
        ...


class BaseBenchmarkEngine:
    name = "base"

    def __init__(self, config: Any) -> None:
        self.config = config
        self._system: KotaemonTextRAGSystem | None = None
        self._text_system: KotaemonTextRAGSystem | None = None

    @property
    def max_context_length(self) -> int:
        value = _config_value(self.config, "max_context_length", 16000)
        return int(value) if value is not None else 16000

    def run(
        self,
        *,
        example: Any,
        documents: list[Any],
    ) -> EngineRunResult:
        raise NotImplementedError(
            f"{type(self).__name__} is an adapter shell; runner integration is pending."
        )

    def _truncate_context(self, context: str) -> str:
        return context[: self.max_context_length]

    def _get_system(self) -> KotaemonTextRAGSystem:
        if self._system is None:
            self._system = KotaemonTextRAGSystem(self._benchmark_config())
        return self._system

    def _get_text_system(self) -> KotaemonTextRAGSystem:
        if self._text_system is None:
            config = self._benchmark_config(retrieval_mode="text")
            self._text_system = KotaemonTextRAGSystem(config)
        return self._text_system

    def _benchmark_config(self, **overrides: Any) -> BenchmarkConfig:
        if isinstance(self.config, BenchmarkConfig):
            return replace(self.config, **overrides) if overrides else self.config
        if isinstance(self.config, dict):
            payload: dict[str, Any] = {
                "suite_name": "benchmark",
                "output_dir": Path("benchmark/artifacts"),
                "engine": self.name,
                "scope": "document",
                "route": "all",
                "cost_profile": None,
                "cache_mode": "warm",
                "reader_mode": "default",
                "retrieval_mode": "hybrid",
                "chunk_size": 1024,
                "chunk_overlap": 256,
                "top_k": 5,
                "max_context_length": 16000,
                "embedding_name": None,
                "reranker_name": None,
                "llm_name": None,
                "reasoning_type": None,
                "agent_mode": None,
                "task_type": None,
                "artifact_type": None,
                "use_generation": True,
                "prompt_template": None,
            }
            payload.update(self.config)
            payload.update(overrides)
            payload["output_dir"] = Path(payload["output_dir"])
            return BenchmarkConfig(**payload)
        return cast(BenchmarkConfig, self.config)

    def _generate_from_context(
        self, example: Any, context: str
    ) -> tuple[str, str, float, dict[str, Any]]:
        system = self._get_system()
        synthetic_hit = RetrievedDocument(
            text=context,
            metadata={"file_name": self.name, "element_type": "context"},
            score=1.0,
        )
        return system._generate_answer(example, [synthetic_hit])

    def document_reports(self) -> list[dict[str, Any]]:
        if self._system is None:
            system_reports = []
        else:
            system_reports = self._system.document_reports()
        if self._text_system is None:
            return system_reports
        return system_reports + self._text_system.document_reports()


class LegacyTextRAGEngine(BaseBenchmarkEngine):
    name = "legacy_text_rag"

    def run(
        self,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
    ) -> EngineRunResult:
        prediction = self._get_system().run_example_documents(documents, example)
        return _prediction_to_result(prediction)


class KotaemonTextRAGEngine(BaseBenchmarkEngine):
    name = "kotaemon-text-rag"

    def run(
        self,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
    ) -> EngineRunResult:
        prediction = self._get_system().run_example_documents(documents, example)
        return _prediction_to_result(prediction)


class DocQARuntimeEngine(BaseBenchmarkEngine):
    name = "docqa_runtime"
    _PAGE_RE = re.compile(r"(?:#page:|page[:\s]+)([\w.-]+)", flags=re.IGNORECASE)

    def __init__(self, config: Any) -> None:
        super().__init__(config)
        self._runtime: Any | None = None
        self._indexed_paths: set[str] = set()

    def _get_runtime(self) -> Any:
        if self._runtime is None:
            from ktem.docqa import DocQARuntime

            self._runtime = DocQARuntime()
        return self._runtime

    def _resolve_indexed_file_id(
        self, runtime: Any, document: BenchmarkDocument
    ) -> str:
        document_path = Path(document.path)
        document_path_text = str(document_path)
        normalized_document_path = _normalized_path(document_path_text)

        try:
            records = list(runtime.list_files())
        except Exception:
            records = []

        for record in records:
            record_path = str(getattr(record, "path", "") or "")
            if (
                record_path
                and _normalized_path(record_path) == normalized_document_path
            ):
                return str(getattr(record, "file_id", "") or "")

        exact_name_matches = [
            record
            for record in records
            if str(getattr(record, "name", "") or "").lower()
            == document_path.name.lower()
        ]
        if len(exact_name_matches) == 1:
            return str(getattr(exact_name_matches[0], "file_id", "") or "")

        for ref in (document.document_id, document_path.name, document_path_text):
            try:
                resolved = runtime.resolve_file_refs([ref])
            except Exception:
                resolved = []
            if len(resolved) == 1:
                return str(getattr(resolved[0], "file_id", "") or "")

        return ""

    def _index_documents(self, documents: list[BenchmarkDocument]) -> list[str]:
        runtime = self._get_runtime()
        selected_ids: list[str] = []
        missing_documents: list[BenchmarkDocument] = []

        for document in documents:
            file_id = self._resolve_indexed_file_id(runtime, document)
            if file_id:
                if file_id not in selected_ids:
                    selected_ids.append(file_id)
                self._indexed_paths.add(str(document.path))
            else:
                missing_documents.append(document)

        missing_paths = [
            str(document.path)
            for document in missing_documents
            if str(document.path) not in self._indexed_paths
        ]
        if missing_paths:
            runtime.index_paths(missing_paths, reindex=False)
            self._indexed_paths.update(missing_paths)

        for document in missing_documents:
            file_id = self._resolve_indexed_file_id(runtime, document)
            if file_id and file_id not in selected_ids:
                selected_ids.append(file_id)
        return selected_ids

    def _docqa_request_kwargs(
        self,
        *,
        example: Any,
        selected_file_ids: list[str],
        active_record: Any,
    ) -> dict[str, Any]:
        return {
            "prompt": _field_value(example, "question", ""),
            "selected_file_ids": selected_file_ids or None,
            "qa_scope": str(
                _config_value(self.config, "scope", None)
                or _field_value(example, "scope", "document")
            ).replace("-", "_"),
            "active_file_id": getattr(active_record, "file_id", ""),
            "active_file_name": getattr(active_record, "name", ""),
            "page_number": _first_evidence_page(example),
            "llm": _config_value(self.config, "llm_name", None),
            "use_citation": _config_value(self.config, "docqa_citation_mode", None),
            "reasoning_type": _config_value(self.config, "reasoning_type", None),
            "agent_mode": _config_value(self.config, "agent_mode", None),
            "task_type": _config_value(self.config, "task_type", None),
            "artifact_type": _config_value(self.config, "artifact_type", None),
            **cf.controller_config_kwargs(
                lambda key: _config_value(self.config, key, None)
            ),
            "origin": "benchmark",
        }

    def run(
        self,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
    ) -> EngineRunResult:
        from ktem.docqa import DocQARequest

        runtime = self._get_runtime()
        start = time.perf_counter()
        selected_file_ids = self._index_documents(documents)
        index_seconds = time.perf_counter() - start
        active_record = None
        if selected_file_ids:
            try:
                records = runtime.resolve_file_refs([selected_file_ids[0]])
                active_record = records[0] if records else None
            except Exception:
                active_record = None

        generation_start = time.perf_counter()
        response = runtime.run_turn(
            DocQARequest(
                **self._docqa_request_kwargs(
                    example=example,
                    selected_file_ids=selected_file_ids,
                    active_record=active_record,
                )
            )
        )
        generation_seconds = time.perf_counter() - generation_start
        predicted_sources = _extract_citations(response.references_text)
        predicted_pages = self._PAGE_RE.findall(response.references_text or "")

        return EngineRunResult(
            answer=response.answer,
            predicted_pages=predicted_pages,
            predicted_sources=predicted_sources,
            retrieved_hits=[],
            timings={
                "index_seconds": index_seconds,
                "generation_seconds": generation_seconds,
            },
            context_preview=response.references_text[: self.max_context_length],
            agent_trace=list(getattr(response, "agent_trace", []) or []),
            evidence_metadata=dict(getattr(response, "evidence_metadata", {}) or {}),
            **cf.controller_response_kwargs(response),
            claim_verification=dict(getattr(response, "claim_verification", {}) or {}),
            presentation=dict(getattr(response, "presentation", {}) or {}),
            retrieval_trace=[
                {
                    "engine": self.name,
                    "selected_file_ids": selected_file_ids,
                    "reasoning_type": _config_value(
                        self.config, "reasoning_type", None
                    ),
                    "agent_mode": _config_value(self.config, "agent_mode", None),
                    "references_text": response.references_text[:2000],
                }
            ],
        )


class DirectPasteEngine(BaseBenchmarkEngine):
    name = "direct_paste"

    def select_context(self, *, documents: list[Any], example: Any) -> str:
        del example
        return self._truncate_context(_join_document_texts(documents))

    def run(
        self,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
    ) -> EngineRunResult:
        system = self._get_text_system()
        parsed_indexes = [system._build_index(document) for document in documents]
        context = self._truncate_context(_parsed_indexes_to_context(parsed_indexes))
        (
            answer,
            _evidence,
            generation_seconds,
            evidence_metadata,
        ) = self._generate_from_context(example, context)
        timings = {
            "parse_seconds": sum(item.parse_seconds for item in parsed_indexes),
            "index_seconds": sum(item.index_seconds for item in parsed_indexes),
            "generation_seconds": generation_seconds,
        }
        return EngineRunResult(
            answer=answer,
            predicted_pages=cast(list[int | str], _all_context_pages(parsed_indexes)),
            predicted_sources=[
                f"{parsed_index.document.document_id}#full"
                for parsed_index in parsed_indexes
            ],
            retrieved_hits=[
                {
                    "document_id": parsed_index.document.document_id,
                    "file_name": parsed_index.document.path.name,
                    "score": 1.0,
                    "selection": "full_text",
                }
                for parsed_index in parsed_indexes
            ],
            timings=timings,
            performance=_performance_from_timings(timings, parsed_indexes),
            cache=_parsed_indexes_cache(parsed_indexes),
            context_preview=context,
            evidence_metadata=evidence_metadata,
            retrieval_trace=[
                {
                    "engine": self.name,
                    "selection": "full_text",
                    "context_characters": len(context),
                }
            ],
        )


class OraclePageEngine(BaseBenchmarkEngine):
    name = "oracle_page"

    def select_context(self, *, documents: list[Any], example: Any) -> str:
        wanted_pages = _evidence_page_set(example)
        selected_texts: list[str] = []

        if wanted_pages:
            for document in documents:
                for page in _document_pages(document):
                    page_number = _field_value(page, "page", None)
                    if page_number is None:
                        page_number = _field_value(page, "page_number", None)
                    if _normalize_page(page_number) in wanted_pages:
                        text = _extract_text(page)
                        if text:
                            selected_texts.append(text)

        context = (
            "\n\n".join(selected_texts)
            if selected_texts
            else _join_document_texts(documents)
        )
        return self._truncate_context(context)

    def run(
        self,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
    ) -> EngineRunResult:
        system = self._get_text_system()
        parsed_indexes = [system._build_index(document) for document in documents]
        wanted_pages = _evidence_page_set(example)
        context = self._truncate_context(
            _parsed_indexes_to_context(parsed_indexes, wanted_pages=wanted_pages)
            or _parsed_indexes_to_context(parsed_indexes)
        )
        (
            answer,
            _evidence,
            generation_seconds,
            evidence_metadata,
        ) = self._generate_from_context(example, context)
        timings = {
            "parse_seconds": sum(item.parse_seconds for item in parsed_indexes),
            "index_seconds": sum(item.index_seconds for item in parsed_indexes),
            "generation_seconds": generation_seconds,
        }
        return EngineRunResult(
            answer=answer,
            predicted_pages=sorted(_evidence_page_set(example), key=str),
            predicted_sources=[
                f"{parsed_index.document.document_id}#page:{page}"
                for parsed_index in parsed_indexes
                for page in sorted(wanted_pages, key=str)
            ],
            retrieved_hits=[
                {
                    "document_id": parsed_index.document.document_id,
                    "page_label": page,
                    "score": 1.0,
                    "selection": "gold_pages",
                }
                for parsed_index in parsed_indexes
                for page in sorted(wanted_pages, key=str)
            ],
            timings=timings,
            performance=_performance_from_timings(timings, parsed_indexes),
            cache=_parsed_indexes_cache(parsed_indexes),
            context_preview=context,
            evidence_metadata=evidence_metadata,
            retrieval_trace=[
                {
                    "engine": self.name,
                    "selection": "gold_pages" if wanted_pages else "full_text",
                    "pages": sorted(wanted_pages, key=str),
                    "context_characters": len(context),
                }
            ],
        )


_ENGINE_TYPES: dict[str, type[BaseBenchmarkEngine]] = {
    LegacyTextRAGEngine.name: LegacyTextRAGEngine,
    KotaemonTextRAGEngine.name: KotaemonTextRAGEngine,
    DocQARuntimeEngine.name: DocQARuntimeEngine,
    DirectPasteEngine.name: DirectPasteEngine,
    OraclePageEngine.name: OraclePageEngine,
}


def get_engine(name: str, config: Any) -> BenchmarkEngine:
    try:
        engine_type = _ENGINE_TYPES[name]
    except KeyError as exc:
        supported = ", ".join(sorted(_ENGINE_TYPES))
        raise ValueError(
            f"Unknown benchmark engine {name!r}. Supported engines: {supported}."
        ) from exc
    return engine_type(config)


def _config_value(config: Any, key: str, default: Any) -> Any:
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def _field_value(item: Any, key: str, default: Any) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _extract_text(item: Any) -> str:
    for key in ("text", "content", "page_text", "full_text"):
        value = _field_value(item, key, None)
        if value:
            return str(value)

    pages = _document_pages(item)
    if pages:
        page_texts = [_extract_text(page) for page in pages]
        return "\n\n".join(text for text in page_texts if text)

    return ""


def _document_pages(document: Any) -> list[Any]:
    pages = _field_value(document, "pages", None)
    if pages is None:
        return []
    return list(pages)


def _join_document_texts(documents: list[Any]) -> str:
    texts = [_extract_text(document) for document in documents]
    return "\n\n".join(text for text in texts if text)


def _prediction_to_result(prediction: dict[str, Any]) -> EngineRunResult:
    return EngineRunResult(
        answer=str(prediction.get("predicted_answer") or ""),
        predicted_pages=list(prediction.get("predicted_pages") or []),
        predicted_sources=list(prediction.get("predicted_sources") or []),
        predicted_element_ids=list(prediction.get("predicted_element_ids") or []),
        retrieved_hits=list(prediction.get("retrieved_hits") or []),
        timings=dict(prediction.get("timings") or {}),
        performance=dict(prediction.get("performance") or {}),
        cache=dict(prediction.get("cache") or {}),
        cost=dict(prediction.get("cost") or {}),
        context_preview=str(prediction.get("context_preview") or ""),
        retrieval_trace=list(prediction.get("retrieval_trace") or []),
        agent_trace=list(prediction.get("agent_trace") or []),
        evidence_metadata=dict(prediction.get("evidence_metadata") or {}),
        **cf.controller_prediction_kwargs(prediction),
        claim_verification=dict(prediction.get("claim_verification") or {}),
        presentation=dict(prediction.get("presentation") or {}),
    )


def _parsed_indexes_to_context(parsed_indexes: list[Any], wanted_pages=None) -> str:
    wanted_pages = {
        str(page).strip() for page in wanted_pages or [] if str(page).strip()
    }
    chunks: list[str] = []
    for parsed_index in parsed_indexes:
        for document in parsed_index.parsed_documents:
            page = _normalize_page(
                document.metadata.get("page_label")
                or document.metadata.get("page_number")
                or document.metadata.get("page")
            )
            if wanted_pages and page not in wanted_pages:
                continue
            text = str(getattr(document, "text", "") or "").strip()
            if not text:
                continue
            label = f"[{parsed_index.document.document_id}"
            if page:
                label += f" page {page}"
            label += "]"
            chunks.append(f"{label}\n{text}")
    return "\n\n".join(chunks)


def _all_context_pages(parsed_indexes: list[Any]) -> list[str]:
    pages: list[str] = []
    for parsed_index in parsed_indexes:
        for document in parsed_index.parsed_documents:
            page = _normalize_page(
                document.metadata.get("page_label")
                or document.metadata.get("page_number")
                or document.metadata.get("page")
            )
            if page and page not in pages:
                pages.append(page)
    return pages


def _evidence_page_set(example: Any) -> set[str]:
    pages = {
        _normalize_page(page) for page in _field_value(example, "evidence_pages", [])
    }
    for evidence in _field_value(example, "gold_evidence", []):
        page = _field_value(evidence, "page", None)
        if page is None:
            page = _field_value(evidence, "page_number", None)
        if page is not None:
            pages.add(_normalize_page(page))
    return {page for page in pages if page}


def _first_evidence_page(example: Any) -> int | None:
    for page in _field_value(example, "evidence_pages", []):
        try:
            return int(str(page).strip())
        except (TypeError, ValueError):
            continue
    for evidence in _field_value(example, "gold_evidence", []):
        page = _field_value(evidence, "page", None)
        if page is None:
            page = _field_value(evidence, "page_number", None)
        try:
            return int(str(page).strip())
        except (TypeError, ValueError):
            continue
    return None


def _normalize_page(page: Any) -> str:
    return str(page).strip()


def _normalized_path(path: str) -> str:
    try:
        return str(Path(path).resolve()).lower()
    except Exception:
        return str(path or "").strip().lower()


def _extract_citations(text: str) -> list[str]:
    citations: list[str] = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if "#page:" in stripped and stripped not in citations:
            citations.append(stripped)
    return citations

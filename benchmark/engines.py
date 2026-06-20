from __future__ import annotations

import re
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol, cast, runtime_checkable

from kotaemon.base import RetrievedDocument

from . import controller_fields as cf
from .benchmark_prompts import runtime_prompt_for
from .docqa_evidence_projection import (
    evidence_element_ids,
    evidence_pages,
    evidence_sources,
    metadata_page_coverage,
    metadata_page_coverage_sources,
    retrieved_hits_from_docqa_evidence,
)
from .docqa_image_documents import (
    is_image_only_document,
    page_image_records_from_documents,
)
from .docqa_runtime_sources import (
    canonicalize_docqa_citations,
    canonicalize_docqa_hits,
    document_paths,
    has_search_index,
    normalized_path,
    selected_source_fallback_hits,
    selected_source_fallback_text,
    unindexed_document_paths,
)
from .engine_accessors import active_runtime_record, config_value, field_value
from .engine_context import (
    all_context_pages,
    document_pages,
    evidence_page_set,
    extract_citations,
    extract_text,
    first_evidence_page,
    join_document_texts,
    normalize_page,
    parsed_indexes_to_context,
)
from .engine_helpers import _parsed_indexes_cache, _performance_from_timings
from .engine_result import EngineRunResult
from .engine_result_adapters import prediction_to_result
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
        value = config_value(self.config, "max_context_length", 16000)
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
                "planner_backend": None,
                "graph_mode": None,
                "visual_retriever_backend": None,
                "visual_generator_backend": None,
                "generator_backend": None,
                "artifact_detail": "compact",
                "use_generation": True,
                "benchmark_prompt_policy": "benchmark_v1",
                "benchmark_prompt_profile": "auto",
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
        return prediction_to_result(prediction)


class KotaemonTextRAGEngine(BaseBenchmarkEngine):
    name = "kotaemon-text-rag"

    def run(
        self,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
    ) -> EngineRunResult:
        prediction = self._get_system().run_example_documents(documents, example)
        return prediction_to_result(prediction)


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
        normalized_document_path = normalized_path(document_path_text)

        try:
            records = list(runtime.list_files())
        except Exception:
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
        reindex_documents: list[BenchmarkDocument] = []

        for document in documents:
            if is_image_only_document(document):
                continue
            file_id = self._resolve_indexed_file_id(runtime, document)
            if file_id:
                if has_search_index(runtime, file_id):
                    if file_id not in selected_ids:
                        selected_ids.append(file_id)
                    self._indexed_paths.add(str(document.path))
                else:
                    reindex_documents.append(document)
            else:
                missing_documents.append(document)

        missing_paths = unindexed_document_paths(
            missing_documents,
            indexed_paths=self._indexed_paths,
        )
        if missing_paths:
            runtime.index_paths(missing_paths, reindex=False)
            self._indexed_paths.update(missing_paths)

        reindex_paths = document_paths(reindex_documents)
        if reindex_paths:
            runtime.index_paths(reindex_paths, reindex=True)
            self._indexed_paths.update(reindex_paths)

        for document in missing_documents + reindex_documents:
            file_id = self._resolve_indexed_file_id(runtime, document)
            if file_id and file_id not in selected_ids:
                selected_ids.append(file_id)
        return selected_ids

    def _docqa_request_kwargs(
        self,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
        selected_file_ids: list[str],
        active_record: Any,
    ) -> dict[str, Any]:
        config = self._benchmark_config()
        return {
            "prompt": runtime_prompt_for(
                example, config, dataset_name=config.suite_name
            ),
            "selected_file_ids": selected_file_ids,
            "page_image_records": page_image_records_from_documents(documents),
            "qa_scope": str(
                config_value(self.config, "scope", None)
                or field_value(example, "scope", "document")
            ).replace("-", "_"),
            "active_file_id": getattr(active_record, "file_id", ""),
            "active_file_name": getattr(active_record, "name", ""),
            "page_number": first_evidence_page(example),
            "selected_text": selected_source_fallback_text(
                documents,
                selected_file_ids,
            ),
            "llm": config_value(self.config, "llm_name", None),
            "use_citation": config_value(self.config, "docqa_citation_mode", None),
            "max_context_length": self.max_context_length,
            "reasoning_type": config_value(self.config, "reasoning_type", None),
            "agent_mode": config_value(self.config, "agent_mode", None),
            "task_type": config_value(self.config, "task_type", None),
            "artifact_type": config_value(self.config, "artifact_type", None),
            "graph_mode": config_value(self.config, "graph_mode", None),
            "visual_retriever_backend": config_value(
                self.config,
                "visual_retriever_backend",
                None,
            ),
            "visual_generator_backend": config_value(
                self.config,
                "visual_generator_backend",
                None,
            ),
            **cf.controller_config_kwargs(
                lambda key: config_value(self.config, key, None)
            ),
            "origin": "benchmark",
        }

    def _response_evidence_outputs(
        self,
        *,
        response: Any,
        documents: list[BenchmarkDocument],
        selected_file_ids: list[str],
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[str],
        list[str],
        list[int | str],
    ]:
        evidence_bundle = dict(getattr(response, "evidence_bundle", {}) or {})
        evidence_metadata = dict(getattr(response, "evidence_metadata", {}) or {})
        retrieved_hits = retrieved_hits_from_docqa_evidence(
            evidence_bundle,
            evidence_metadata,
        )
        reference_citations = canonicalize_docqa_citations(
            extract_citations(response.references_text),
            documents,
            selected_file_ids,
        )
        answer_citations = canonicalize_docqa_citations(
            extract_citations(getattr(response, "answer", "")),
            documents,
            selected_file_ids,
        )
        predicted_citations = list(answer_citations)
        predicted_citations.extend(
            citation
            for citation in reference_citations
            if citation not in predicted_citations
        )
        reference_pages = self._PAGE_RE.findall(response.references_text or "")
        if not retrieved_hits and not reference_citations and not reference_pages:
            retrieved_hits = selected_source_fallback_hits(documents, selected_file_ids)
        retrieved_hits = canonicalize_docqa_hits(
            retrieved_hits,
            documents,
            selected_file_ids,
        )
        predicted_sources = evidence_sources(retrieved_hits)
        predicted_sources.extend(
            source for source in reference_citations if source not in predicted_sources
        )
        predicted_sources.extend(
            source
            for source in metadata_page_coverage_sources(
                evidence_metadata,
                documents,
                selected_file_ids,
            )
            if source not in predicted_sources
        )
        predicted_pages: list[int | str] = list(evidence_pages(retrieved_hits))
        predicted_pages.extend(
            page for page in reference_pages if page not in predicted_pages
        )
        predicted_pages.extend(
            page
            for page in metadata_page_coverage(evidence_metadata)
            if page not in predicted_pages
        )
        return (
            evidence_metadata,
            retrieved_hits,
            predicted_sources,
            predicted_citations,
            predicted_pages,
        )

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
        active_record = active_runtime_record(runtime, selected_file_ids)

        generation_start = time.perf_counter()
        response = runtime.run_turn(
            DocQARequest(
                **self._docqa_request_kwargs(
                    example=example,
                    documents=documents,
                    selected_file_ids=selected_file_ids,
                    active_record=active_record,
                )
            )
        )
        generation_seconds = time.perf_counter() - generation_start
        (
            evidence_metadata,
            retrieved_hits,
            predicted_sources,
            predicted_citations,
            predicted_pages,
        ) = self._response_evidence_outputs(
            response=response,
            documents=documents,
            selected_file_ids=selected_file_ids,
        )
        return EngineRunResult(
            answer=response.answer,
            predicted_pages=predicted_pages,
            predicted_sources=predicted_sources,
            predicted_citations=predicted_citations,
            predicted_element_ids=evidence_element_ids(retrieved_hits),
            retrieved_hits=retrieved_hits,
            timings={
                "index_seconds": index_seconds,
                "generation_seconds": generation_seconds,
            },
            context_preview=response.references_text[: self.max_context_length],
            agent_trace=list(getattr(response, "agent_trace", []) or []),
            evidence_metadata=evidence_metadata,
            **cf.controller_response_kwargs(response),
            claim_verification=dict(getattr(response, "claim_verification", {}) or {}),
            presentation=dict(getattr(response, "presentation", {}) or {}),
            retrieval_trace=[
                {
                    "engine": self.name,
                    "selected_file_ids": selected_file_ids,
                    "reasoning_type": config_value(self.config, "reasoning_type", None),
                    "agent_mode": config_value(self.config, "agent_mode", None),
                    "references_text": response.references_text[:2000],
                }
            ],
        )


class DirectPasteEngine(BaseBenchmarkEngine):
    name = "direct_paste"

    def select_context(self, *, documents: list[Any], example: Any) -> str:
        del example
        return self._truncate_context(join_document_texts(documents))

    def run(
        self,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
    ) -> EngineRunResult:
        system = self._get_text_system()
        parsed_indexes = [system._build_index(document) for document in documents]
        context = self._truncate_context(parsed_indexes_to_context(parsed_indexes))
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
            predicted_pages=cast(list[int | str], all_context_pages(parsed_indexes)),
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
        wanted_pages = evidence_page_set(example)
        selected_texts: list[str] = []

        if wanted_pages:
            for document in documents:
                for page in document_pages(document):
                    page_number = field_value(page, "page", None)
                    if page_number is None:
                        page_number = field_value(page, "page_number", None)
                    if normalize_page(page_number) in wanted_pages:
                        text = extract_text(page)
                        if text:
                            selected_texts.append(text)

        context = (
            "\n\n".join(selected_texts)
            if selected_texts
            else join_document_texts(documents)
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
        wanted_pages = evidence_page_set(example)
        context = self._truncate_context(
            parsed_indexes_to_context(parsed_indexes, wanted_pages=wanted_pages)
            or parsed_indexes_to_context(parsed_indexes)
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
            predicted_pages=sorted(evidence_page_set(example), key=str),
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

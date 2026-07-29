from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol, cast, runtime_checkable

from kotaemon.base import RetrievedDocument
from kotaemon.docqa_request_policies import BENCHMARK_REQUEST_POLICY

from . import controller_fields as cf
from .alce_answer_grounding import (
    alce_grounding_stage_event,
    apply_alce_answer_grounding,
)
from .docqa_controller_context import controller_request_context
from .docqa_evidence_projection import evidence_element_ids
from .docqa_image_documents import (
    element_index_records_from_documents,
    page_image_records_from_documents,
)
from .docqa_index_cache import DocQAIndexCache
from .docqa_response_projection import response_evidence_outputs
from .docqa_runtime_sources import (
    selected_source_fallback_text,
    source_identity_crosswalk,
)
from .engine_accessors import active_runtime_record, config_value, field_value
from .engine_context import (
    all_context_pages,
    document_pages,
    evidence_page_set,
    extract_text,
    join_document_texts,
    normalize_page,
    parsed_indexes_to_context,
)
from .engine_helpers import _parsed_indexes_cache, _performance_from_timings
from .engine_result import EngineRunResult
from .engine_result_adapters import prediction_to_result
from .performance_timing import runtime_timing_payload
from .schemas import BenchmarkConfig, BenchmarkDocument
from .system import KotaemonTextRAGSystem


@runtime_checkable
class BenchmarkEngine(Protocol):
    name: str

    def task_contract_llm(self) -> Any:
        ...

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

    def task_contract_llm(self) -> Any:
        """Return the shared judge used by engine-independent task contracts."""
        return self._get_text_system().llm

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
                "benchmark_answer_mode": "scoring_adapter_v1",
                "benchmark_no_think": False,
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
    _response_evidence_outputs = staticmethod(response_evidence_outputs)
    _shared_prepared_file_ids: dict[tuple[Any, ...], str] = {}

    def __init__(self, config: Any) -> None:
        super().__init__(config)
        self._runtime: Any | None = None
        self._index_cache = DocQAIndexCache(
            config,
            shared_prepared_file_ids=self._shared_prepared_file_ids,
        )
        self._indexed_paths = self._index_cache.indexed_paths
        self._prepared_file_ids = self._index_cache.prepared_file_ids
        self._last_index_cache: dict[str, Any] = {}
        self._active_route_trace: list[dict[str, Any]] = []
        self._active_timings: dict[str, float] = {}
        self._active_stage_started_at: float | None = None

    def _get_runtime(self) -> Any:
        if self._runtime is None:
            from ktem.docqa import DocQARuntime

            self._runtime = DocQARuntime()
        return self._runtime

    def _index_documents(self, documents: list[BenchmarkDocument]) -> list[str]:
        selected_ids = self._index_cache.index_documents(
            self._get_runtime(),
            documents,
        )
        self._last_index_cache = dict(self._index_cache.last_trace)
        return selected_ids

    def prepare_examples(self, bundle: Any, examples: list[Any]) -> None:
        documents: list[BenchmarkDocument] = []
        seen_document_ids: set[str] = set()
        for example in examples:
            for document_id in example.document_ids or [example.document_id]:
                if document_id in seen_document_ids:
                    continue
                document = bundle.documents.get(document_id)
                if document is None:
                    continue
                seen_document_ids.add(document_id)
                documents.append(document)
        if documents:
            self._index_documents(documents)

    def _docqa_request_kwargs(
        self,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
        selected_file_ids: list[str],
        active_record: Any,
    ) -> dict[str, Any]:
        policy = BENCHMARK_REQUEST_POLICY
        config = self._benchmark_config()
        crosswalk = source_identity_crosswalk(documents, selected_file_ids)
        for document, record in zip(documents, crosswalk):
            document.source_identity_crosswalk = [dict(record)]
        return {
            **controller_request_context(
                example, config, lambda key: config_value(self.config, key, None)
            ),
            "selected_file_ids": selected_file_ids,
            "source_identity_crosswalk": crosswalk,
            "page_image_records": page_image_records_from_documents(documents),
            "element_index_records": element_index_records_from_documents(documents),
            "qa_scope": str(
                config_value(self.config, "scope", None)
                or field_value(example, "scope", policy.qa_scope_default)
            ).replace("-", "_"),
            "active_file_id": getattr(active_record, "file_id", ""),
            "active_file_name": getattr(active_record, "name", ""),
            "page_number": None,
            "selected_text": selected_source_fallback_text(
                documents,
                selected_file_ids,
            ),
            "llm": config_value(self.config, "llm_name", None),
            "use_citation": config_value(self.config, "docqa_citation_mode", None),
            "max_context_length": self.max_context_length,
            "route_timeout_seconds": config_value(
                self.config,
                "route_timeout_seconds",
                None,
            ),
            "reasoning_type": config_value(self.config, "reasoning_type", None),
            "agent_mode": config_value(self.config, "agent_mode", None),
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
            "origin": policy.origin,
        }

    def run(
        self,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
    ) -> EngineRunResult:
        runtime = self._get_runtime()
        selected_file_ids, index_seconds = self._prepare_runtime_documents(documents)
        active_record = active_runtime_record(runtime, selected_file_ids)
        response, runtime_turn_seconds = self._run_runtime_generation(
            runtime,
            example=example,
            documents=documents,
            selected_file_ids=selected_file_ids,
            active_record=active_record,
        )
        return self._runtime_result(
            response,
            example=example,
            documents=documents,
            selected_file_ids=selected_file_ids,
            index_seconds=index_seconds,
            runtime_turn_seconds=runtime_turn_seconds,
        )

    def _prepare_runtime_documents(
        self,
        documents: list[BenchmarkDocument],
    ) -> tuple[list[str], float]:
        self._active_route_trace = [
            {
                "stage": "document_index_resolution",
                "status": "started",
            }
        ]
        self._active_timings = {}
        self._active_stage_started_at = time.perf_counter()
        start = time.perf_counter()
        selected_file_ids = self._index_documents(documents)
        index_seconds = time.perf_counter() - start
        self._active_timings["index_seconds"] = index_seconds
        self._active_route_trace[-1].update(
            {
                "status": "completed",
                "seconds": round(index_seconds, 4),
                "cache": dict(self._last_index_cache),
            }
        )
        return selected_file_ids, index_seconds

    def _run_runtime_generation(
        self,
        runtime: Any,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
        selected_file_ids: list[str],
        active_record: Any,
    ) -> tuple[Any, float]:
        from ktem.docqa import DocQARequest

        self._active_route_trace.append(
            {
                "stage": "runtime_turn",
                "status": "started",
            }
        )
        self._active_stage_started_at = time.perf_counter()
        runtime_turn_start = time.perf_counter()
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
        runtime_turn_seconds = time.perf_counter() - runtime_turn_start
        self._active_timings["runtime_turn_seconds"] = runtime_turn_seconds
        self._active_route_trace[-1].update(
            {
                "status": "completed",
                "seconds": round(runtime_turn_seconds, 4),
            }
        )
        self._active_stage_started_at = None
        return response, runtime_turn_seconds

    def _runtime_result(
        self,
        response: Any,
        *,
        example: Any,
        documents: list[BenchmarkDocument],
        selected_file_ids: list[str],
        index_seconds: float,
        runtime_turn_seconds: float,
    ) -> EngineRunResult:
        (
            evidence_metadata,
            retrieved_hits,
            predicted_sources,
            predicted_citations,
            predicted_pages,
        ) = response_evidence_outputs(
            response=response,
            documents=documents,
            selected_file_ids=selected_file_ids,
        )
        answer, grounding_trace, grounding_seconds = apply_alce_answer_grounding(
            suite_name=str(config_value(self.config, "suite_name", "") or ""),
            llm_factory=lambda: self._get_text_system().llm,
            question=str(field_value(example, "question", "") or ""),
            candidate_answer=response.answer,
            evidence_items=list(evidence_metadata.get("evidence") or retrieved_hits),
        )
        if grounding_trace:
            evidence_metadata["alce_answer_grounding"] = grounding_trace
            self._active_route_trace.append(
                alce_grounding_stage_event(grounding_trace, grounding_seconds)
            )
        timings, performance = runtime_timing_payload(
            evidence_metadata,
            index_seconds=index_seconds,
            runtime_turn_seconds=runtime_turn_seconds,
            grounding_seconds=grounding_seconds,
        )
        return EngineRunResult(
            answer=answer,
            predicted_pages=predicted_pages,
            predicted_sources=predicted_sources,
            predicted_citations=predicted_citations,
            predicted_element_ids=evidence_element_ids(retrieved_hits),
            retrieved_hits=retrieved_hits,
            timings=timings,
            performance=performance,
            cache={"document_index": dict(self._last_index_cache)},
            context_preview=response.references_text[: self.max_context_length],
            agent_trace=list(getattr(response, "agent_trace", []) or []),
            evidence_metadata=evidence_metadata,
            **cf.controller_response_kwargs(response),
            claim_verification=dict(getattr(response, "claim_verification", {}) or {}),
            presentation=dict(getattr(response, "presentation", {}) or {}),
            source_identity_crosswalk=source_identity_crosswalk(
                documents,
                selected_file_ids,
            ),
            retrieval_trace=[
                *self._active_route_trace,
                {
                    "engine": self.name,
                    "selected_file_ids": selected_file_ids,
                    "reasoning_type": config_value(
                        self.config,
                        "reasoning_type",
                        None,
                    ),
                    "agent_mode": config_value(self.config, "agent_mode", None),
                    "references_text": response.references_text[:2000],
                },
            ],
        )

    def route_timeout_diagnostics(self) -> dict[str, Any]:
        trace = [dict(item) for item in self._active_route_trace]
        timings = dict(self._active_timings)
        if (
            trace
            and trace[-1].get("status") == "started"
            and self._active_stage_started_at is not None
        ):
            elapsed = time.perf_counter() - self._active_stage_started_at
            trace[-1]["elapsed_before_timeout_seconds"] = round(elapsed, 4)
            stage = str(trace[-1].get("stage") or "")
            if stage == "document_index_resolution":
                timings["index_seconds"] = elapsed
            elif stage == "generation":
                timings["generation_seconds"] = elapsed
        return {
            "retrieval_trace": trace,
            "timings": timings,
            "cache": {"document_index": dict(self._last_index_cache)},
        }


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
    if name == "benchmark_direct_answer":
        from .benchmark_direct_answer import BenchmarkDirectAnswerEngine

        return BenchmarkDirectAnswerEngine(config)
    try:
        engine_type = _ENGINE_TYPES[name]
    except KeyError as exc:
        supported = ", ".join(sorted([*_ENGINE_TYPES, "benchmark_direct_answer"]))
        raise ValueError(
            f"Unknown benchmark engine {name!r}. Supported engines: {supported}."
        ) from exc
    return engine_type(config)

from __future__ import annotations

from typing import Any

from kotaemon.docqa_request_policies import BENCHMARK_REQUEST_POLICY

from . import controller_fields as cf
from . import generation_contract
from .benchmark_prompts import build_benchmark_prompt
from .docqa_runtime_sources import (
    selected_source_fallback_text,
    selected_source_title,
    source_identity_crosswalk,
)
from .engine_accessors import config_value, field_value
from .schemas import BenchmarkConfig, BenchmarkDocument


def docqa_request_kwargs(
    engine: Any,
    *,
    example: Any,
    documents: list[BenchmarkDocument],
    selected_file_ids: list[str],
    active_record: Any,
    page_image_builder: Any,
    element_index_builder: Any,
) -> dict[str, Any]:
    policy = BENCHMARK_REQUEST_POLICY
    config = engine._benchmark_config()
    crosswalk = source_identity_crosswalk(documents, selected_file_ids)
    for document, record in zip(documents, crosswalk):
        document.source_identity_crosswalk = [dict(record)]
    return {
        **controller_request_context(
            example, config, lambda key: config_value(engine.config, key, None)
        ),
        "selected_file_ids": selected_file_ids,
        "source_identity_crosswalk": crosswalk,
        "page_image_records": page_image_builder(documents),
        "element_index_records": element_index_builder(documents),
        "qa_scope": str(
            config_value(engine.config, "scope", None)
            or field_value(example, "scope", policy.qa_scope_default)
        ).replace("-", "_"),
        "active_file_id": getattr(active_record, "file_id", ""),
        "active_file_name": getattr(active_record, "name", ""),
        "page_number": None,
        "selected_text": selected_source_fallback_text(
            documents,
            selected_file_ids,
        ),
        "selected_source_title": selected_source_title(
            documents,
            selected_file_ids,
        ),
        "llm": config_value(engine.config, "llm_name", None),
        "use_citation": config_value(engine.config, "docqa_citation_mode", None),
        "max_context_length": engine.max_context_length,
        "route_timeout_seconds": config_value(
            engine.config,
            "route_timeout_seconds",
            None,
        ),
        "route_deadline_monotonic": engine._route_deadline_monotonic,
        **generation_contract.benchmark_request_generation_config(),
        "reasoning_type": config_value(engine.config, "reasoning_type", None),
        "agent_mode": config_value(engine.config, "agent_mode", None),
        "artifact_type": config_value(engine.config, "artifact_type", None),
        "graph_mode": config_value(engine.config, "graph_mode", None),
        "visual_retriever_backend": config_value(
            engine.config,
            "visual_retriever_backend",
            None,
        ),
        "visual_generator_backend": config_value(
            engine.config,
            "visual_generator_backend",
            None,
        ),
        "origin": policy.origin,
    }


def controller_request_context(example: Any, config: BenchmarkConfig, config_getter):
    prompt = build_benchmark_prompt(example, config, dataset_name=config.suite_name)
    controller_domain = controller_dataset_family(example, config)
    controller_kwargs = cf.controller_config_kwargs(config_getter)
    if controller_domain and not controller_kwargs.get("verification_domain"):
        controller_kwargs["verification_domain"] = controller_domain
    if controller_domain == "qasper" and not controller_kwargs.get("verification_mode"):
        controller_kwargs["verification_mode"] = "strict"
    if controller_domain == "slidevqa" and not controller_kwargs.get(
        "verification_mode"
    ):
        controller_kwargs["verification_mode"] = "light"
    if controller_domain == "mmdocrag" and not controller_kwargs.get(
        "verification_mode"
    ):
        controller_kwargs["verification_mode"] = "strict"
    if controller_domain == "ragtruth":
        controller_kwargs["allowed_routes"] = ["doc_text"]
        controller_kwargs["verification_mode"] = "off"
    configured_task_type = config_getter("task_type")
    if configured_task_type:
        runtime_task_type = configured_task_type
    elif controller_domain == "qasper":
        runtime_task_type = "qasper_qa"
    else:
        runtime_task_type = field_value(example, "answer_type", None)
    return {
        "prompt": prompt.runtime_prompt,
        "controller_question": prompt.retrieval_query,
        "retrieval_query": prompt.retrieval_query,
        "dataset_family": controller_domain,
        "task_type": runtime_task_type,
        "answer_type": field_value(example, "answer_type", runtime_task_type),
        "modality": field_value(example, "modality", None),
        **controller_kwargs,
    }


def controller_dataset_family(example: Any, config: BenchmarkConfig) -> str:
    metadata = dict(getattr(example, "metadata", {}) or {})
    values = [
        config_value(config, "verification_domain", None),
        metadata.get("dataset_family"),
        metadata.get("domain"),
        metadata.get("mixed_source_manifest"),
        config_value(config, "suite_name", None),
    ]
    text = " ".join(str(value or "").lower() for value in values)
    if "multimodal_doc_qa" in text or "mmdocrag" in text:
        return "mmdocrag"
    if "slide_qa" in text or "slidevqa" in text:
        return "slidevqa"
    if "financebench" in text or "finance" in text:
        return "finance"
    if "scientific_qa" in text or "qasper" in text:
        return "qasper"
    if "hallucination_verification" in text or "ragtruth" in text:
        return "ragtruth"
    if "citation_quality" in text or "alce" in text:
        return "alce"
    return str(config_value(config, "verification_domain", None) or "").strip()

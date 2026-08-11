from __future__ import annotations

from typing import Any

from . import controller_fields as cf
from .benchmark_prompts import build_benchmark_prompt
from .engine_accessors import config_value, field_value
from .schemas import BenchmarkConfig


def controller_request_context(example: Any, config: BenchmarkConfig, config_getter):
    prompt = build_benchmark_prompt(example, config, dataset_name=config.suite_name)
    controller_domain = controller_dataset_family(example, config)
    controller_kwargs = cf.controller_config_kwargs(config_getter)
    if controller_domain and not controller_kwargs.get("verification_domain"):
        controller_kwargs["verification_domain"] = controller_domain
    if controller_domain == "qasper" and not controller_kwargs.get("verification_mode"):
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

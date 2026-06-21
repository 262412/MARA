from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .schemas import BenchmarkConfig, BenchmarkExample

BENCHMARK_PROMPT_MARKER = "Benchmark prompt contract:"

ALCE_PROMPT_SOURCE = "princeton-nlp/ALCE prompts/asqa_default.json"
ALCE_QAMPARI_PROMPT_SOURCE = "princeton-nlp/ALCE prompts/qampari_default.json"
RAGTRUTH_PROMPT_SOURCE = "ParticleMedia/RAGTruth baseline/dataset.py"
QASPER_PROMPT_SOURCE = "allenai/qasper-led-baseline dataset contract"
FINANCEBENCH_PROMPT_SOURCE = "FinanceBench paper Table 3 prompt pattern"
GENERIC_PROMPT_SOURCE = "MARA benchmark generic grounded QA contract"


@dataclass(frozen=True, slots=True)
class BenchmarkPromptBundle:
    raw_question: str
    benchmark_question: str
    runtime_prompt: str
    retrieval_query: str
    policy: str
    profile: str
    prompt_source: str


def build_benchmark_prompt(
    example: BenchmarkExample,
    config: BenchmarkConfig,
    *,
    dataset_name: str | None = None,
) -> BenchmarkPromptBundle:
    raw_question = str(example.question or "").strip()
    policy = str(config.benchmark_prompt_policy or "benchmark_v1").strip().lower()
    benchmark_question = _benchmark_question(example, raw_question)
    retrieval_query = _retrieval_query(example, benchmark_question)
    if policy == "raw":
        return BenchmarkPromptBundle(
            raw_question=raw_question,
            benchmark_question=benchmark_question,
            runtime_prompt=raw_question,
            retrieval_query=raw_question,
            policy="raw",
            profile="raw",
            prompt_source="raw_dataset_question",
        )

    profile = _profile_for_example(example, config, dataset_name=dataset_name)
    prompt_source, runtime_prompt = _runtime_prompt(
        example,
        benchmark_question,
        profile,
        dataset_name=dataset_name or config.suite_name,
    )
    return BenchmarkPromptBundle(
        raw_question=raw_question,
        benchmark_question=benchmark_question,
        runtime_prompt=runtime_prompt,
        retrieval_query=retrieval_query,
        policy=policy,
        profile=profile,
        prompt_source=prompt_source,
    )


def runtime_prompt_for(
    example: BenchmarkExample,
    config: BenchmarkConfig,
    *,
    dataset_name: str | None = None,
) -> str:
    return build_benchmark_prompt(
        example,
        config,
        dataset_name=dataset_name,
    ).runtime_prompt


def generation_prompt_for(
    example: BenchmarkExample,
    config: BenchmarkConfig,
    *,
    context: str,
    dataset_name: str | None = None,
) -> str:
    bundle = build_benchmark_prompt(example, config, dataset_name=dataset_name)
    context_text = str(context or "").strip()
    if bundle.policy == "raw":
        return _raw_generation_prompt(bundle.raw_question, context_text)
    return _insert_context(bundle.runtime_prompt, context_text)


def retrieval_query_for(
    example: BenchmarkExample,
    config: BenchmarkConfig,
    *,
    dataset_name: str | None = None,
) -> str:
    return build_benchmark_prompt(
        example,
        config,
        dataset_name=dataset_name,
    ).retrieval_query


def _benchmark_question(example: BenchmarkExample, raw_question: str) -> str:
    metadata = _metadata(example)
    value = str(metadata.get("benchmark_question") or "").strip()
    return value or raw_question


def _retrieval_query(example: BenchmarkExample, benchmark_question: str) -> str:
    metadata = _metadata(example)
    value = str(metadata.get("retrieval_query") or "").strip()
    return value or benchmark_question


def _metadata(example: BenchmarkExample) -> dict[str, Any]:
    return dict(getattr(example, "metadata", {}) or {})


def _profile_for_example(
    example: BenchmarkExample,
    config: BenchmarkConfig,
    *,
    dataset_name: str | None,
) -> str:
    explicit = str(config.benchmark_prompt_profile or "auto").strip().lower()
    if explicit != "auto":
        return explicit

    dataset = str(dataset_name or config.suite_name or "").strip().lower()
    modality = str(example.modality or "").strip().lower()
    answer_type = str(example.answer_type or "").strip().lower()
    family = str(_metadata(example).get("dataset_family") or "").strip().lower()
    route_policy = str(config.route_policy or "").strip().lower()

    if _looks_visual(dataset, modality, family, route_policy):
        return "visual_grounded_qa"
    if "ragtruth" in dataset or "verification" in answer_type:
        return "guardrail_grounded_qa"
    if "alce" in dataset or "citation" in answer_type or family == "citation_quality":
        return "citation_grounded_qa"
    return "concise_grounded_qa"


def _looks_visual(
    dataset: str,
    modality: str,
    family: str,
    route_policy: str,
) -> bool:
    visual_datasets = ("slidevqa", "docvqa", "vidore", "mmdocrag")
    visual_modalities = ("image", "page_image", "visual", "multimodal", "mixed")
    return (
        any(name in dataset for name in visual_datasets)
        or modality in visual_modalities
        or family in {"visual_retrieval", "multimodal_doc_qa"}
        or route_policy in {"visual", "page_image", "page-image"}
    )


def _runtime_prompt(
    example: BenchmarkExample,
    question: str,
    profile: str,
    *,
    dataset_name: str | None,
) -> tuple[str, str]:
    dataset = str(dataset_name or "").strip().lower()
    if "ragtruth" in dataset:
        return RAGTRUTH_PROMPT_SOURCE, _ragtruth_prompt(example, question)
    if "alce" in dataset and _is_qampari_example(example, dataset_name=dataset):
        return ALCE_QAMPARI_PROMPT_SOURCE, _alce_qampari_prompt(question)
    if "alce" in dataset:
        return ALCE_PROMPT_SOURCE, _alce_prompt(question)
    if "qasper" in dataset:
        return QASPER_PROMPT_SOURCE, _qasper_prompt(question)
    if "financebench" in dataset:
        return FINANCEBENCH_PROMPT_SOURCE, _financebench_prompt(question)
    return GENERIC_PROMPT_SOURCE, _generic_prompt(question, profile)


def _prompt_header(source: str) -> str:
    return f"{BENCHMARK_PROMPT_MARKER}\nPrompt source: {source}\n"


def _alce_prompt(question: str) -> str:
    return (
        _prompt_header(ALCE_PROMPT_SOURCE)
        + "Instruction: Write an accurate, engaging, and concise answer for "
        "the given question using only the provided search results and cite "
        "them properly. Use an unbiased and journalistic tone. Always cite for "
        "any factual claim. When citing several search results, use [1][2][3]. "
        "Cite at least one document and at most three documents in each "
        "sentence. If multiple documents support the sentence, only cite a "
        "minimum sufficient subset of the documents.\n\n"
        f"Question: {question}\n\n"
        f"{_concise_answer_contract()}\n\n"
        "Answer:"
    )


def _alce_qampari_prompt(question: str) -> str:
    return (
        _prompt_header(ALCE_QAMPARI_PROMPT_SOURCE)
        + "Instruction: Provide a list of accurate answers for the given "
        "question using only the provided search results and cite them "
        "properly. Always cite one and only one document for each answer. "
        "Separate answers by commas. For questions that have more than 5 "
        "answers, write at least 5 answers. Return a comma-separated list. "
        "Do not write a paragraph or explanatory commentary.\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


def _ragtruth_prompt(example: BenchmarkExample, question: str) -> str:
    metadata = _metadata(example)
    source_info = _first_present(
        metadata.get("source_info"),
        metadata.get("reference"),
        metadata.get("related_passages"),
        _first_gold_evidence_span(example),
    )
    response = _first_present(metadata.get("response"), _first_answer(example))
    task_type = str(metadata.get("task_type") or "QA").strip() or "QA"
    if task_type.lower() == "qa":
        source_block = (
            f"Below is a question:\n{question}\n\n"
            f"Below are related passages:\n{source_info}\n\n"
            f"Below is an answer:\n{response}\n\n"
        )
    elif task_type.lower() == "data2txt":
        source_block = (
            f"Below is the structured JSON data:\n{source_info}\n\n"
            f"Below is an overview of the data:\n{response}\n\n"
        )
    else:
        source_block = (
            f"Below is the original source:\n{source_info}\n\n"
            f"Below is a summary or response:\n{response}\n\n"
        )
    return (
        _prompt_header(RAGTRUTH_PROMPT_SOURCE)
        + source_block
        + "Your task is to determine whether the response contains either or "
        "both of the following two types of hallucinations:\n"
        "1. conflict: instances where the response presents direct "
        "contradiction or opposition to the source;\n"
        "2. baseless info: instances where the response includes information "
        "which is not substantiated by or inferred from the source.\n"
        "Then, compile the labeled hallucinated spans into a JSON dict with "
        'a key "hallucination list" and its value as a list of hallucinated '
        'spans. If hallucinations exist, output {"hallucination list": '
        "[hallucination span1, hallucination span2, ...]}. Otherwise, output "
        '{"hallucination list": []}.\n'
        "Output:"
    )


def _qasper_prompt(question: str) -> str:
    return (
        _prompt_header(QASPER_PROMPT_SOURCE)
        + "Answer the question using only the provided research paper context "
        "or evidence. Return only the answer span, yes/no value, or "
        '"unanswerable" when the evidence does not answer the question. Keep '
        "free-form answers short and do not add background commentary.\n\n"
        f"Question: {question}\n\n"
        f"{_concise_answer_contract()}\n\n"
        "Answer:"
    )


def _financebench_prompt(question: str) -> str:
    return (
        _prompt_header(FINANCEBENCH_PROMPT_SOURCE)
        + f"Answer this question: {question}\n\n"
        + _concise_answer_contract()
        + "\n\n"
        + _numeric_answer_contract()
        + "\n\n"
        "Answer:"
    )


def _generic_prompt(question: str, profile: str) -> str:
    return (
        _prompt_header(GENERIC_PROMPT_SOURCE)
        + f"Question: {question}\n\n"
        + _concise_answer_contract()
        + "\n"
        + _numeric_answer_contract()
        + "\n"
        + _profile_instructions(profile)
        + "\n\n"
        "Answer:"
    )


def _concise_answer_contract() -> str:
    return (
        "Answer contract:\n"
        "- Start with the direct answer.\n"
        "- If the question asks for a single name, date, time, amount, count, "
        "or yes/no answer, return only that value unless evidence is "
        "insufficient.\n"
        "- Keep the answer concise and benchmark-comparable.\n"
        "- Do not include hidden reasoning, chain-of-thought, or scratch work."
    )


def _numeric_answer_contract() -> str:
    return (
        "Numeric/calculation contract:\n"
        "- For numeric or calculation questions, give the final value first, "
        "then at most one short formula or source phrase needed to justify it.\n"
        "- If a calculation cannot be completed, name the missing operand "
        "explicitly; do not give a generic context-insufficient explanation.\n"
        "- Do not use tables unless the expected answer format asks for one."
    )


def _profile_instructions(profile: str) -> str:
    profile_instructions = {
        "concise_grounded_qa": (
            "- Answer using the selected document evidence.\n"
            "- Prefer the shortest complete answer that preserves the required "
            "numeric, factual, or yes/no conclusion."
        ),
        "citation_grounded_qa": (
            "- Answer using the selected document evidence and include compact "
            "citations when evidence is available.\n"
            "- Keep citations attached to the claims they support."
        ),
        "guardrail_grounded_qa": (
            "- Judge whether the response or claim is supported by the selected "
            "source evidence.\n"
            "- Separate supported, unsupported, and insufficient-evidence "
            "conclusions clearly."
        ),
        "visual_grounded_qa": (
            "- Answer using visual or multimodal page evidence when it is the "
            "best support.\n"
            "- Cite the relevant page or visual evidence when available."
        ),
    }
    return profile_instructions[profile]


def _insert_context(runtime_prompt: str, context: str) -> str:
    context_block = f"Retrieved evidence context:\n{context}" if context else ""
    prompt = runtime_prompt.rstrip()
    if prompt.endswith("Answer:"):
        stem = prompt[: -len("Answer:")].rstrip()
        return f"{stem}\n\n{context_block}\n\nAnswer:".strip()
    if prompt.endswith("Output:"):
        stem = prompt[: -len("Output:")].rstrip()
        return f"{stem}\n\n{context_block}\n\nOutput:".strip()
    return f"{prompt}\n\n{context_block}\n\nAnswer:".strip()


def _raw_generation_prompt(question: str, context: str) -> str:
    return f"Question: {question}\n\nContext:\n{context}\n\nAnswer:".strip()


def _first_present(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _first_answer(example: BenchmarkExample) -> str:
    for answer in getattr(example, "answers", []) or []:
        text = str(answer or "").strip()
        if text:
            return text
    return ""


def _first_gold_evidence_span(example: BenchmarkExample) -> str:
    for item in getattr(example, "gold_evidence", []) or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("span") or "").strip()
        if text:
            return text
    return ""


def _is_qampari_example(example: BenchmarkExample, *, dataset_name: str) -> bool:
    metadata = _metadata(example)
    task = str(metadata.get("alce_task") or metadata.get("task") or "").lower()
    answer_type = str(example.answer_type or "").lower()
    return (
        "qampari" in dataset_name
        or task == "qampari"
        or answer_type in {"list_qa", "list"}
    )

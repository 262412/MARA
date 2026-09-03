from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ragtruth_source_context import ragtruth_source_context
from .schemas import BenchmarkConfig, BenchmarkExample

BENCHMARK_PROMPT_MARKER = "Benchmark prompt contract:"
GOLD_ANSWER_PROMPT_MARKER = "Benchmark gold-answer contract:"

ALCE_PROMPT_SOURCE = "princeton-nlp/ALCE prompts/asqa_default.json"
ALCE_QAMPARI_PROMPT_SOURCE = "princeton-nlp/ALCE prompts/qampari_default.json"
RAGTRUTH_PROMPT_SOURCE = "ParticleMedia/RAGTruth baseline/dataset.py"
RAGTRUTH_EVALUATION_QUESTION = (
    "Which exact spans in the response are unsupported by the source?"
)
QASPER_PROMPT_SOURCE = "allenai/qasper-led-baseline dataset contract"
FINANCEBENCH_PROMPT_SOURCE = "FinanceBench paper Table 3 prompt pattern"
GENERIC_PROMPT_SOURCE = "MARA benchmark generic grounded QA contract"
GOLD_ANSWER_PROMPT_SOURCE = "MARA benchmark gold-answer answer-only contract"
MIN_PROMPT_TEXT_BUDGET_CHARS = 512
RAGTRUTH_TASK_PROMPT_BUDGET_CHARS = 12000
PROMPT_TEXT_TRUNCATION_NOTICE = "[truncated to fit benchmark prompt budget]"


@dataclass(frozen=True, slots=True)
class BenchmarkPromptBundle:
    raw_question: str
    benchmark_question: str
    runtime_prompt: str
    retrieval_query: str
    policy: str
    profile: str
    prompt_source: str
    no_think: bool


def build_benchmark_prompt(
    example: BenchmarkExample,
    config: BenchmarkConfig,
    *,
    dataset_name: str | None = None,
) -> BenchmarkPromptBundle:
    raw_question = str(example.question or "").strip()
    policy = str(config.benchmark_prompt_policy or "benchmark_v1").strip().lower()
    benchmark_question = _benchmark_question(example, raw_question)
    no_think = _no_think_enabled(config, policy)
    if policy == "raw":
        return BenchmarkPromptBundle(
            raw_question=raw_question,
            benchmark_question=benchmark_question,
            runtime_prompt=_maybe_no_think(raw_question, no_think),
            retrieval_query=raw_question,
            policy="raw",
            profile="raw",
            prompt_source="raw_dataset_question",
            no_think=no_think,
        )

    prompt_budget_chars = _prompt_text_budget_chars(config)
    benchmark_question = _truncate_prompt_text(
        benchmark_question,
        prompt_budget_chars,
    )
    retrieval_query = _truncate_prompt_text(
        _retrieval_query(example, benchmark_question),
        prompt_budget_chars,
    )
    profile = _profile_for_example(example, config, dataset_name=dataset_name)
    if policy == "gold_answer_v1":
        dataset = str(dataset_name or config.suite_name or "").strip().lower()
        if "ragtruth" in dataset:
            prompt_source = RAGTRUTH_PROMPT_SOURCE
            runtime_prompt = _ragtruth_prompt(
                example,
                benchmark_question,
                prompt_budget_chars=prompt_budget_chars,
            )
        else:
            prompt_source = GOLD_ANSWER_PROMPT_SOURCE
            runtime_prompt = _gold_answer_prompt(
                benchmark_question,
                profile,
                dataset_name=dataset,
            )
    else:
        prompt_source, runtime_prompt = _runtime_prompt(
            example,
            benchmark_question,
            profile,
            dataset_name=dataset_name or config.suite_name,
            prompt_budget_chars=prompt_budget_chars,
        )
    return BenchmarkPromptBundle(
        raw_question=raw_question,
        benchmark_question=benchmark_question,
        runtime_prompt=_maybe_no_think(runtime_prompt, no_think),
        retrieval_query=retrieval_query,
        policy=policy,
        profile=profile,
        prompt_source=prompt_source,
        no_think=no_think,
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


def _prompt_text_budget_chars(config: BenchmarkConfig) -> int:
    value = int(getattr(config, "max_context_length", 0) or 0)
    return max(value, MIN_PROMPT_TEXT_BUDGET_CHARS)


def _truncate_prompt_text(text: str, max_chars: int) -> str:
    value = str(text or "").strip()
    if len(value) <= max_chars:
        return value
    notice = f"\n\n{PROMPT_TEXT_TRUNCATION_NOTICE}"
    body_chars = max_chars - len(notice)
    if body_chars <= 0:
        return PROMPT_TEXT_TRUNCATION_NOTICE[:max_chars]
    return f"{value[:body_chars].rstrip()}{notice}"


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
    prompt_budget_chars: int,
) -> tuple[str, str]:
    dataset = str(dataset_name or "").strip().lower()
    if "ragtruth" in dataset:
        return RAGTRUTH_PROMPT_SOURCE, _ragtruth_prompt(
            example,
            question,
            prompt_budget_chars=prompt_budget_chars,
        )
    if "alce" in dataset and _is_qampari_example(example, dataset_name=dataset):
        return ALCE_QAMPARI_PROMPT_SOURCE, _alce_qampari_prompt(question)
    if "alce" in dataset:
        return ALCE_PROMPT_SOURCE, _alce_prompt(question)
    if "qasper" in dataset:
        return QASPER_PROMPT_SOURCE, _qasper_prompt(
            question,
            typed_only="qasper_typed" in dataset,
        )
    if "financebench" in dataset:
        return FINANCEBENCH_PROMPT_SOURCE, _financebench_prompt(question)
    return GENERIC_PROMPT_SOURCE, _generic_prompt(question, profile)


def _prompt_header(source: str) -> str:
    return f"{BENCHMARK_PROMPT_MARKER}\nPrompt source: {source}\n"


def _gold_prompt_header(source: str) -> str:
    return f"{GOLD_ANSWER_PROMPT_MARKER}\nPrompt source: {source}\n"


def _no_think_enabled(config: BenchmarkConfig, policy: str) -> bool:
    return bool(getattr(config, "benchmark_no_think", False)) or policy == (
        "gold_answer_v1"
    )


def _maybe_no_think(prompt: str, enabled: bool) -> str:
    text = str(prompt or "").strip()
    if not enabled or text.startswith("/no_think"):
        return text
    return f"/no_think\n{text}"


def _gold_answer_prompt(
    question: str, profile: str, *, dataset_name: str | None
) -> str:
    dataset = str(dataset_name or "").strip().lower()
    parts = [
        _gold_prompt_header(GOLD_ANSWER_PROMPT_SOURCE),
        "Use the provided evidence only. Return only the gold-answer value "
        "that should be compared against the dataset reference answer.",
        "Do not provide explanation, reasoning, markdown bullets, or citations "
        "unless the dataset answer itself requires citations.",
    ]
    if "ragtruth" in dataset:
        parts.append(
            "For RAGTruth-style examples, output only the JSON object with key "
            '"hallucination list" and no surrounding commentary.'
        )
    elif "alce" in dataset and "qampari" in dataset:
        parts.append(
            "For QAMPARI-style examples, output a comma-separated answer list "
            "without a paragraph."
        )
    elif "qasper_typed" in dataset:
        parts.append(
            'For this typed QASPER suite, output exactly "yes", "no", or '
            '"unanswerable".'
        )
    elif "qasper" in dataset:
        parts.append(
            'For QASPER-style examples, output only the answer span, "yes", '
            '"no", or "unanswerable". For a free-form answer, choose the '
            "shortest complete span or comma-separated spans directly supported "
            "by the evidence. Do not add explanations, background, or any "
            "claim beyond those spans."
        )
    elif "financebench" in dataset:
        parts.append(
            "For FinanceBench-style examples, output the final name, number, "
            "date, percentage, currency amount, or yes/no value only."
        )
    elif profile == "visual_grounded_qa":
        parts.append(
            "For visual/page QA, output the visible answer text exactly as it "
            "should be scored."
        )
    else:
        parts.append(
            "If the answer is a number or calculation result, output only the "
            "final value. If evidence is insufficient, output "
            '"unanswerable".'
        )
    parts.append(f"Question: {question}")
    parts.append("Answer:")
    return "\n\n".join(parts)


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


def _ragtruth_prompt(
    example: BenchmarkExample,
    question: str,
    *,
    prompt_budget_chars: int,
) -> str:
    prompt_budget_chars = max(
        prompt_budget_chars,
        RAGTRUTH_TASK_PROMPT_BUDGET_CHARS,
    )
    metadata = _metadata(example)
    source_info = _first_present(
        metadata.get("source_info"),
        metadata.get("reference"),
        metadata.get("related_passages"),
        _first_gold_evidence_span(example),
    )
    response = _first_present(metadata.get("response"), _first_answer(example))
    evaluation_question = str(
        metadata.get("benchmark_question") or RAGTRUTH_EVALUATION_QUESTION
    ).strip()
    task_type = str(metadata.get("task_type") or "QA").strip().lower() or "qa"
    labels = _ragtruth_block_labels(task_type)
    instruction = (
        "Detect exact response spans that conflict with the source or add "
        "baseless information. Use only the source. Return JSON only as "
        '{"hallucination list": ["exact unsupported span"]}; return an empty '
        "list when every response claim is supported."
    )
    output_guard = 'Return exactly one JSON object with the key "hallucination list".'
    fixed = (
        _prompt_header(RAGTRUTH_PROMPT_SOURCE)
        + instruction
        + f"\n\n{labels[0]}{evaluation_question}"
        + f"\n\n{labels[1]}\n\n{labels[2]}\n\n"
        + output_guard
        + "\nAnswer:"
    )
    available = max(0, prompt_budget_chars - len(fixed))
    source_budget = int(available * 0.6)
    response_budget = max(0, available - source_budget)
    blocks = (
        ragtruth_source_context(
            source_info,
            response,
            budget=source_budget,
            structured=task_type == "data2txt",
        ),
        _truncate_ragtruth_block(response, response_budget),
    )
    prompt = (
        _prompt_header(RAGTRUTH_PROMPT_SOURCE)
        + instruction
        + f"\n\n{labels[0]}{evaluation_question}\n\n"
        + f"{labels[1]}{blocks[0]}\n\n"
        + f"{labels[2]}{blocks[1]}\n\n"
        + output_guard
        + "\nAnswer:"
    )
    return prompt[:prompt_budget_chars]


def _ragtruth_block_labels(task_type: str) -> tuple[str, str, str]:
    if task_type == "data2txt":
        return (
            "Below is a question:\n",
            "Below is the structured JSON data:\n",
            "Below is an overview of the data:\n",
        )
    if task_type == "qa":
        return (
            "Below is a question:\n",
            "Below are related passages:\n",
            "Below is an answer:\n",
        )
    return (
        "Below is a question:\n",
        "Below is the original source:\n",
        "Below is a summary or response:\n",
    )


def _truncate_ragtruth_block(value: Any, budget: int) -> str:
    text = str(value or "").strip()
    if budget <= 0:
        return ""
    return text[:budget].rstrip()


def _qasper_prompt(question: str, *, typed_only: bool = False) -> str:
    if typed_only:
        answer_contract = (
            'Return exactly one label: "yes", "no", or "unanswerable". '
            "Do not return an answer span, number, list, or explanation."
        )
    else:
        answer_contract = (
            "Return only the answer span, yes/no value, or "
            '"unanswerable" when the evidence does not answer the question. '
            "Keep free-form answers short and do not add background commentary. "
            "Use the shortest complete answer supported by the evidence; do not "
            "combine supported facts with extra claims or explain the context."
        )
    return (
        _prompt_header(QASPER_PROMPT_SOURCE)
        + "Answer the question using only the provided research paper context "
        f"or evidence. {answer_contract} For a yes/no question, do not default "
        "to yes: choose either polarity only when an explicit paper statement "
        "entails it. Phrases such as no, not, without, failed to, or did not "
        "can directly support a no answer; mere absence from the retrieved "
        "excerpt cannot.\n\n"
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

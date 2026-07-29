from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import fitz

FINANCE_CASES = {
    "financebench_id_03029": {
        "same_parent_distinct_year_cells",
        "header_or_caption_dimension",
    },
    "financebench_id_07507": {
        "same_parent_distinct_year_cells",
        "materialized_parent_operand",
        "multi_period_percentage_change",
    },
    "financebench_id_02987": {"materialized_parent_operand"},
    "financebench_id_07966": {"multi_period_percentage_change"},
}
FINANCE_NEGATIVE_REQUIREMENTS = {"missing_execution_requirement_abstains"}
FINANCE_FIXED_PAGE_MAPPINGS = {
    ("ADOBE_2016_10K", 61): 62,
    ("ACTIVISIONBLIZZARD_2019_10K", 72): 73,
}
QASPER_CASES = {
    "50be4a737dc0951b35d139f51075011095d77f2a": {"ordinary_free_text"},
    "2cd37743bcc7ea3bd405ce6d91e79e5339d7642e": {"yes_no"},
    "1dc2da5078a7e5ea82ccd1c90d81999a922bc9bf": {"support_and_contradiction"},
    "206739417251064b910ae9e5ff096e867ee10fb8": {"answerability_rewrite"},
}
QASPER_SYNTHETIC_REQUIREMENTS = {
    "support_and_contradiction",
    "cross_page_required_slots",
    "answerability_rewrite",
}
DEFAULT_RUN_ROOT = Path(
    "/mnt/scratch/users/tbczhang/outputs/MARA/contract_smoke_round1"
)
DEFAULT_BASELINE_ROOT = Path(
    "/mnt/scratch/users/tbczhang/outputs/MARA/"
    "final_thesis_benchmark_statistical_20260705_fullsystem_postfix/manifests"
)


def contract_route(*, verification_domain: str) -> dict[str, Any]:
    return {
        "route_id": "contract_hybrid",
        "route_name": "Contract hybrid",
        "engine": "docqa_runtime",
        "scope": "multi_document",
        "reader_mode": "default",
        "retrieval_mode": "hybrid",
        "top_k": 16,
        "use_generation": True,
        "reasoning_type": "mara",
        "max_context_length": 3000,
        "route_timeout_seconds": 240.0,
        "controller_mode": "off",
        "docqa_citation_mode": "inline",
        "route_policy": "hybrid",
        "allowed_routes": ["hybrid"],
        "verification_mode": "strict",
        "verification_domain": verification_domain,
        "text_retriever_backend": "BAAI/bge-m3",
        "planner_backend": "heuristic_local",
        "generator_backend": "Qwen/Qwen3-8B",
        "benchmark_role": "qa_quality",
        "headline_role": "deployed_policy",
        "benchmark_prompt_policy": "gold_answer_v1",
        "benchmark_no_think": True,
    }


def write_qasper_cross_page_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = fitz.open()
    pages = (
        (
            "Contract Smoke Study - Methods",
            (
                "The authors released the code publicly with the paper.",
                "The release statement applies to the final evaluated system.",
            ),
        ),
        (
            "Contract Smoke Study - Correction",
            (
                "The authors did not release the code for the final evaluated system.",
                "This correction explicitly supersedes the earlier release statement.",
            ),
        ),
    )
    for page_number, (title, lines) in enumerate(pages, start=1):
        page = pdf.new_page(width=612, height=792)
        page.insert_text((72, 72), title, fontsize=16, fontname="hebo")
        y = 118
        for line in lines:
            page.insert_text((72, y), line, fontsize=12, fontname="helv")
            y += 24
        page.insert_text((500, 744), f"Page {page_number}", fontsize=10)
    pdf.save(str(path))
    pdf.close()


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or int(payload.get("schema_version") or 1) != 2:
        raise ValueError(f"Expected a schema_version=2 manifest: {path}")
    return payload


def _selected_examples(
    source: dict[str, Any],
    cases: dict[str, set[str]],
) -> list[dict[str, Any]]:
    by_id = {
        str(item.get("example_id") or ""): item
        for item in source.get("examples") or []
        if isinstance(item, dict)
    }
    missing = sorted(set(cases) - set(by_id))
    if missing:
        raise ValueError("Missing contract smoke examples: " + ", ".join(missing))
    selected = []
    for example_id, requirements in cases.items():
        item = copy.deepcopy(by_id[example_id])
        metadata = dict(item.get("metadata") or {})
        metadata["contract_smoke_requirements"] = sorted(requirements)
        item["metadata"] = metadata
        selected.append(item)
    return selected


def _selected_documents(
    source: dict[str, Any],
    examples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    document_ids = {
        str(document_id)
        for example in examples
        for document_id in (example.get("document_ids") or [example.get("document_id")])
        if str(document_id or "").strip()
    }
    documents = [
        copy.deepcopy(item)
        for item in source.get("documents") or []
        if isinstance(item, dict) and str(item.get("document_id") or "") in document_ids
    ]
    found = {str(item.get("document_id") or "") for item in documents}
    if found != document_ids:
        raise ValueError(
            "Missing contract smoke documents: "
            + ", ".join(sorted(document_ids - found))
        )
    return documents


def _finance_negative_example(
    source_example: dict[str, Any],
) -> dict[str, Any]:
    item = copy.deepcopy(source_example)
    item.update(
        {
            "example_id": "finance_contract_missing_period_2099",
            "question": (
                "What was Adobe's percentage change in unadjusted operating "
                "income from FY2015 to FY2099?"
            ),
            "answers": ["unanswerable"],
            "answer_type": "numeric",
            "evidence_pages": [],
            "evidence_sources": [],
            "gold_evidence": [],
            "expected_guardrails": {"allow_abstention": True},
        }
    )
    metadata = dict(item.get("metadata") or {})
    metadata.update(
        {
            "contract_smoke_requirements": sorted(FINANCE_NEGATIVE_REQUIREMENTS),
            "contract_smoke_mutation": "missing_period_operand_2099",
        }
    )
    item["metadata"] = metadata
    return item


def build_finance_manifest(source_path: Path) -> dict[str, Any]:
    source = _load_manifest(source_path)
    examples = [
        with_audited_finance_page_mappings(example)
        for example in _selected_examples(source, FINANCE_CASES)
    ]
    negative_source = next(
        item for item in examples if item.get("example_id") == "financebench_id_07507"
    )
    examples.append(_finance_negative_example(negative_source))
    return {
        "schema_version": 2,
        "dataset_name": "financebench_contract_smoke",
        "documents": _selected_documents(source, examples),
        "routes": [contract_route(verification_domain="finance")],
        "examples": examples,
        "metadata": {"contract": "contract_smoke_manifest.v1"},
    }


def with_audited_finance_page_mappings(
    example: dict[str, Any],
) -> dict[str, Any]:
    mapped = copy.deepcopy(example)
    gold_evidence = [
        dict(item)
        for item in mapped.get("gold_evidence") or []
        if isinstance(item, dict)
    ]
    for item in gold_evidence:
        document_id = str(
            item.get("document_id")
            or item.get("source_id")
            or mapped.get("document_id")
            or ""
        ).strip()
        current_page = item.get("page", item.get("page_label"))
        try:
            page_number = int(str(current_page))
        except (TypeError, ValueError):
            continue
        dataset_page = item.get("dataset_page")
        runtime_page = page_number
        mapping_source = str(item.get("page_alignment") or "")
        mapping_version = "financebench_page_mapping.v1"
        if (document_id, page_number) in FINANCE_FIXED_PAGE_MAPPINGS:
            dataset_page = page_number
            runtime_page = FINANCE_FIXED_PAGE_MAPPINGS[(document_id, page_number)]
            mapping_source = "financebench_contract_fixed_mapping"
            mapping_version = "financebench_contract_page_mapping.v1"
        if dataset_page in (None, "") or int(str(dataset_page)) == runtime_page:
            continue
        item["dataset_page"] = dataset_page
        item["page"] = runtime_page
        item["citation"] = f"{document_id}#page:{runtime_page}"
        item["page_mapping"] = {
            "dataset_page": dataset_page,
            "runtime_page": runtime_page,
            "mapping_source": mapping_source,
            "mapping_confidence": 1.0,
            "mapping_version": mapping_version,
        }
    mapped["gold_evidence"] = gold_evidence
    runtime_pages = [
        item.get("page") for item in gold_evidence if item.get("page") not in (None, "")
    ]
    runtime_sources = [
        str(item.get("citation") or "")
        for item in gold_evidence
        if str(item.get("citation") or "")
    ]
    if runtime_pages:
        mapped["evidence_pages"] = list(dict.fromkeys(runtime_pages))
    if runtime_sources:
        mapped["evidence_sources"] = list(dict.fromkeys(runtime_sources))
    return mapped


def _qasper_answer_type(example: dict[str, Any]) -> str:
    annotations = [
        item
        for item in dict(example.get("metadata") or {}).get("qasper_answer_annotations")
        or []
        if isinstance(item, dict)
    ]
    if any(item.get("yes_no") is not None for item in annotations):
        return "boolean"
    if annotations and all(bool(item.get("unanswerable")) for item in annotations):
        return "unanswerable"
    return str(example.get("answer_type") or "free_text")


def _qasper_cross_page_example() -> dict[str, Any]:
    return {
        "example_id": "qasper_contract_cross_page_conflict",
        "document_id": "qasper_contract_cross_page",
        "document_ids": ["qasper_contract_cross_page"],
        "scope": "document",
        "modality": "text",
        "answer_type": "boolean",
        "question": "Across pages 1 and 2, did the authors release the code?",
        "answers": ["unanswerable"],
        "evidence_pages": [1, 2],
        "evidence_sources": [
            "qasper_contract_cross_page#page:1",
            "qasper_contract_cross_page#page:2",
        ],
        "gold_evidence": [
            {
                "document_id": "qasper_contract_cross_page",
                "page": 1,
                "citation": "qasper_contract_cross_page#page:1",
                "span": "The authors released the code publicly with the paper.",
            },
            {
                "document_id": "qasper_contract_cross_page",
                "page": 2,
                "citation": "qasper_contract_cross_page#page:2",
                "span": (
                    "The authors did not release the code for the final "
                    "evaluated system."
                ),
            },
        ],
        "expected_guardrails": {"allow_abstention": True},
        "metadata": {
            "dataset_family": "scientific_qa",
            "contract_smoke_requirements": sorted(QASPER_SYNTHETIC_REQUIREMENTS),
            "qasper_answer_annotations": [
                {
                    "extractive_spans": [],
                    "free_form_answer": "",
                    "yes_no": None,
                    "unanswerable": True,
                    "evidence": [],
                }
            ],
        },
    }


def build_qasper_manifest(source_path: Path, fixture_path: Path) -> dict[str, Any]:
    source = _load_manifest(source_path)
    examples = _selected_examples(source, QASPER_CASES)
    for item in examples:
        item["answer_type"] = _qasper_answer_type(item)
    documents = _selected_documents(source, examples)
    documents.append(
        {
            "document_id": "qasper_contract_cross_page",
            "path": str(fixture_path.resolve()),
            "format_type": "pdf",
            "modality": "text",
        }
    )
    examples.append(_qasper_cross_page_example())
    return {
        "schema_version": 2,
        "dataset_name": "qasper_contract_smoke",
        "documents": documents,
        "routes": [contract_route(verification_domain="qasper")],
        "examples": examples,
        "metadata": {"contract": "contract_smoke_manifest.v1"},
    }


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the first FinanceBench/QASPER contract smoke manifests."
    )
    parser.add_argument(
        "--finance-source",
        type=Path,
        default=DEFAULT_BASELINE_ROOT / "financebench-stat150.routes.json",
    )
    parser.add_argument(
        "--qasper-source",
        type=Path,
        default=DEFAULT_BASELINE_ROOT / "qasper-dev-stat200.routes.json",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_RUN_ROOT / "manifests"
    )
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    fixture_path = output_dir / "fixtures/qasper-cross-page-contract.pdf"
    write_qasper_cross_page_pdf(fixture_path)
    finance_path = output_dir / "financebench-contract-smoke.json"
    qasper_path = output_dir / "qasper-contract-smoke.json"
    _write_manifest(
        finance_path,
        build_finance_manifest(args.finance_source.resolve()),
    )
    _write_manifest(
        qasper_path,
        build_qasper_manifest(args.qasper_source.resolve(), fixture_path),
    )
    print(f"finance_manifest={finance_path}")
    print(f"qasper_manifest={qasper_path}")
    print(f"qasper_fixture={fixture_path}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa.boolean_proposition_evidence import classify_boolean_evidence
from ktem.docqa.query_planning import build_query_plan

from benchmark.docqa_index_cache import DocQAIndexCache
from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.schemas import BenchmarkDocument


class _Verifier:
    def __init__(self, responses: str | list[str]) -> None:
        self.responses = [responses] if isinstance(responses, str) else list(responses)
        self.calls: list[str] = []

    def __call__(self, prompt: str, **_kwargs: Any) -> Any:
        self.calls.append(prompt)
        return SimpleNamespace(text=self.responses.pop(0))


class _BudgetVerifier(_Verifier):
    def __call__(self, prompt: str, **kwargs: Any) -> Any:
        assert len(prompt) <= 7000
        return super().__call__(prompt, **kwargs)


def _item(evidence_id: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "results",
        "text": text,
    }


def test_semantic_across_does_not_create_pseudo_cross_page_boolean_plan() -> None:
    plan = build_query_plan(
        "Overall, does having parallel data improve semantic role induction across multiple languages?",
        answer_type="boolean",
        verification_domain="qasper",
    )

    assert plan.question_type == "simple_fact"
    assert [slot.slot_id for slot in plan.evidence_slots] == [
        "support:boolean_proposition"
    ]
    assert plan.constraints["requires_multiple_evidence"] is False
    assert plan.constraints["requires_distinct_source_pages"] is False
    assert plan.constraints["requires_structure"] is False


def test_semantic_between_without_two_subjects_uses_one_boolean_proposition() -> None:
    plan = build_query_plan(
        "Does the method improve between multiple languages?",
        answer_type="boolean",
        verification_domain="qasper",
    )

    assert plan.question_type == "simple_fact"
    assert [slot.slot_id for slot in plan.evidence_slots] == [
        "support:boolean_proposition"
    ]
    assert plan.constraints["requires_multiple_evidence"] is False


def test_complete_verdict_missing_ref_and_quote_gets_one_structural_repair() -> None:
    quote = "The authors released their source code with the paper."
    llm = _Verifier(
        [
            '{"verdict":"yes_complete","evidence_ref":"","evidence_quote":""}',
            json.dumps(
                {
                    "verdict": "yes_complete",
                    "evidence_ref": "E1:S1",
                    "evidence_quote": quote,
                }
            ),
        ]
    )

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the source code with the paper?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("support", quote)],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert len(llm.calls) == 2
    assert result.trace["repair_attempted"] == "true"
    assert result.trace["evidence_ref"] == "E1:S1"
    assert result.trace["evidence_quote"] == quote
    assert "Did the authors release the source code with the paper?" in llm.calls[1]
    assert "You are a QASPER proposition verifier" not in llm.calls[1]
    assert llm.calls[1].count(quote) == 1


@pytest.mark.parametrize(
    ("initial", "repaired"),
    (
        (
            '{"verdict":"yes_complete","evidence_ref":"",'
            '"evidence_quote":"The authors released their source code with the paper."}',
            '{"verdict":"yes_complete","evidence_ref":"E1:S1",'
            '"evidence_quote":"The authors released their source code with the paper."}',
        ),
        (
            '{"verdict":"yes_complete","evidence_ref":"E1:S1",' '"evidence_quote":""}',
            '{"verdict":"yes_complete","evidence_ref":"E1:S1",'
            '"evidence_quote":"The authors released their source code with the paper."}',
        ),
    ),
)
def test_each_missing_lineage_field_gets_at_most_one_repair(
    initial: str,
    repaired: str,
) -> None:
    quote = "The authors released their source code with the paper."
    llm = _Verifier([initial, repaired])

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the source code with the paper?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("support", quote)],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert len(llm.calls) == 2
    assert result.trace["repair_attempted"] == "true"


def test_out_of_buffer_evidence_ref_is_repaired_to_current_packed_ref() -> None:
    quote = "The authors released their source code with the paper."
    llm = _Verifier(
        [
            json.dumps(
                {
                    "verdict": "yes_complete",
                    "evidence_ref": "E9:S1",
                    "evidence_quote": quote,
                }
            ),
            json.dumps(
                {
                    "verdict": "yes_complete",
                    "evidence_ref": "E1:S1",
                    "evidence_quote": quote,
                }
            ),
        ]
    )

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the source code with the paper?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("support", quote)],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert len(llm.calls) == 2
    assert result.trace["evidence_ref"] == "E1:S1"
    assert "Preserve the original evidence_ref" not in llm.calls[1]
    assert "Select evidence_ref only from: E1:S1" in llm.calls[1]


def test_structural_repair_reuses_packed_evidence_within_prompt_budget() -> None:
    quote = "The authors released their source code with the paper."
    items = [_item("support", quote)]
    items.extend(
        _item(
            f"context-{index}",
            (
                f"Source code release context {index}. "
                + "Detailed appendix evidence about the release process. " * 7
            ),
        )
        for index in range(40)
    )
    initial = (
        '{"verdict":"yes_complete","evidence_ref":"","evidence_quote":""}'
        + " trailing malformed verifier output" * 32
    )
    llm = _BudgetVerifier(
        [
            initial,
            json.dumps(
                {
                    "verdict": "yes_complete",
                    "evidence_ref": "E1:S1",
                    "evidence_quote": quote,
                }
            ),
        ]
    )

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the source code with the paper?",
        answer_type="boolean",
        evidence="",
        evidence_items=items,
        required_evidence_ids=["support"],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert len(llm.calls) == 2
    assert max(map(len, llm.calls)) <= 7000
    assert result.trace["repair_prompt_truncated"] == "true"


def test_failed_structural_repair_abstains_instead_of_preserving_yes() -> None:
    quote = "The authors released their source code with the paper."
    llm = _Verifier(
        [
            '{"verdict":"yes_complete","evidence_ref":"","evidence_quote":""}',
            '{"verdict":"yes_complete","evidence_ref":"","evidence_quote":""}',
        ]
    )

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the source code with the paper?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("support", quote)],
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["action"] == "abstained_invalid_verifier_repair"
    assert result.trace["reason"] == "invalid_verifier_schema_after_repair"


def test_paraphrase_quote_abstains_but_exact_quote_is_authoritative() -> None:
    exact = "The authors released their source code with the paper."
    item = _item("support", exact)

    paraphrase_result = verify_qasper_answerability(
        _Verifier(
            json.dumps(
                {
                    "verdict": "yes_complete",
                    "evidence_ref": "E1:S1",
                    "evidence_quote": "The authors published the code with the paper.",
                }
            )
        ),
        question="Did the authors release the source code with the paper?",
        answer_type="boolean",
        evidence=exact,
        evidence_items=[item],
        candidate_answer="yes",
    )
    exact_result = verify_qasper_answerability(
        _Verifier(
            json.dumps(
                {
                    "verdict": "yes_complete",
                    "evidence_ref": "E1:S1",
                    "evidence_quote": exact,
                }
            )
        ),
        question="Did the authors release the source code with the paper?",
        answer_type="boolean",
        evidence=exact,
        evidence_items=[item],
        candidate_answer="unanswerable",
    )

    assert paraphrase_result.answer == "unanswerable"
    assert paraphrase_result.trace["reason"] == "ungrounded_quote"
    assert exact_result.answer == "yes"
    assert exact_result.trace["reason"] == "grounded_complete_proposition"


class _StaleRuntime:
    def __init__(
        self,
        path: Path,
        *,
        current_file_id: str = "cached-file",
        ready: bool = False,
    ) -> None:
        relations = [
            SimpleNamespace(
                source_id=current_file_id,
                relation_type="document",
                target_id="chunk-1",
            )
        ]
        if ready:
            relations.append(
                SimpleNamespace(
                    source_id=current_file_id,
                    relation_type="vector",
                    target_id="chunk-1",
                )
            )
        self.file_index = SimpleNamespace(
            id=1,
            _resources={
                "Index": relations,
                "VectorStore": object(),
            },
            _vs=object(),
        )
        self._path = path
        self._current_file_id = current_file_id
        self.indexed: list[tuple[list[str], bool]] = []

    def list_files(self) -> list[Any]:
        return [
            SimpleNamespace(
                file_id=self._current_file_id,
                path=str(self._path),
                name=self._path.name,
            )
        ]

    def resolve_file_refs(self, _refs: list[str]) -> list[Any]:
        return []

    def load_settings(self) -> dict[str, Any]:
        return {}

    def index_paths(self, paths: list[str], *, reindex: bool, **_kwargs: Any) -> None:
        self.indexed.append((paths, reindex))


def test_prepared_cache_hit_revalidates_stale_runtime_index_and_rebuilds(
    tmp_path,
) -> None:
    path = tmp_path / "paper.txt"
    path.write_text("The paper text.", encoding="utf-8")
    document = BenchmarkDocument("paper", path, format_type="txt")
    config = SimpleNamespace(
        suite_name="qasper-typed159x3",
        route="text_rag",
        route_policy="text",
        chunk_size=512,
        chunk_overlap=64,
    )
    shared: dict[tuple[Any, ...], str] = {}
    cache = DocQAIndexCache(config, shared_prepared_file_ids=shared)
    cache.remember_prepared_file(document, "cached-file")
    runtime = _StaleRuntime(path)

    selected = cache.index_documents(runtime, [document])

    assert selected == ["cached-file"]
    assert runtime.indexed == [([str(path)], True)]
    assert cache.last_trace["hits"] == 1
    assert cache.last_trace["identities"][0]["cache_status"] == "hit_stale"
    cache_key, _identity = cache.document_identity(document)
    assert shared[cache_key] == "cached-file"


def test_prepared_cache_hit_adopts_current_ready_runtime_file_id(tmp_path) -> None:
    path = tmp_path / "paper.txt"
    path.write_text("The paper text.", encoding="utf-8")
    document = BenchmarkDocument("paper", path, format_type="txt")
    config = SimpleNamespace(
        suite_name="qasper-typed159x3",
        route="text_rag",
        route_policy="text",
        chunk_size=512,
        chunk_overlap=64,
    )
    shared: dict[tuple[Any, ...], str] = {}
    cache = DocQAIndexCache(config, shared_prepared_file_ids=shared)
    cache.remember_prepared_file(document, "cached-file")
    runtime = _StaleRuntime(path, current_file_id="current-file", ready=True)

    selected = cache.index_documents(runtime, [document])

    assert selected == ["current-file"]
    assert runtime.indexed == []
    cache_key, _identity = cache.document_identity(document)
    assert shared[cache_key] == "current-file"


def test_external_corpus_does_not_prove_own_data_collection() -> None:
    question = "Did they collect their own data?"
    quote = "The authors collected the data from an external corpus."
    item = _item("external", quote)

    assessment = classify_boolean_evidence(question, "yes", item)
    result = verify_qasper_answerability(
        _Verifier(
            json.dumps(
                {
                    "verdict": "yes_complete",
                    "evidence_ref": "E1:S1",
                    "evidence_quote": quote,
                }
            )
        ),
        question=question,
        answer_type="boolean",
        evidence=quote,
        evidence_items=[item],
        candidate_answer="yes",
    )

    assert assessment.classification != "supports"
    assert result.answer == "unanswerable"


def test_unknown_data_provenance_does_not_prove_own_collection() -> None:
    question = "Did they collect their own data?"
    quote = "We collected data for the experiments."

    assessment = classify_boolean_evidence(question, "yes", _item("unknown", quote))

    assert assessment.classification != "supports"


def test_publicly_available_resources_do_not_prove_own_collection() -> None:
    question = "Did they collect their own data?"
    quote = "We collected our own data from publicly available resources."

    assessment = classify_boolean_evidence(question, "yes", _item("public", quote))

    assert assessment.classification != "supports"


def test_explicit_own_data_provenance_supports_own_collection() -> None:
    question = "Did they collect their own data?"
    quote = "We collected our own data for the experiments."

    assessment = classify_boolean_evidence(question, "yes", _item("own", quote))

    assert assessment.classification == "supports"


def test_generic_data_collection_question_keeps_existing_polarity() -> None:
    question = "Did they collect data?"
    quote = "We collected data from an external corpus."

    assessment = classify_boolean_evidence(question, "yes", _item("generic", quote))

    assert assessment.classification == "supports"

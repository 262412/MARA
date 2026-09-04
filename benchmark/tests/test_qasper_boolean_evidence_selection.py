from __future__ import annotations

import json
from typing import Any

from benchmark.qasper_evidence_priorities import qasper_evidence_priorities
from benchmark.qasper_prompt_budget import fit_qasper_verifier_items


def _item(
    evidence_id: str,
    text: str,
    *,
    section: str = "results",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": section,
        "text": text,
    }


def test_boolean_verifier_packs_closed_language_scope_before_lexical_distractor():
    decisive = (
        "In cooperation with education researchers, we identified current "
        "controversial topics in education in English-speaking countries."
    )
    long_item = _item(
        "language-scope",
        (
            "This section describes our data selection and evaluation process for "
            "creating a new corpus. "
            + (
                "Domain restrictions and non-reported reliability affect data "
                "evaluation results. " * 20
            )
            + decisive
            + " We compiled the selected documents into the raw corpus."
        ),
        section="methods",
    )

    _prompt, bounded, trace = fit_qasper_verifier_items(
        [long_item],
        lambda evidence: f"QUESTION\n{evidence}",
        question="Do they report results only on English data?",
        candidate_answer="no",
        required_evidence_ids=["evidence:paper:language-scope"],
        required_slot_ids=["support:boolean_proposition"],
    )

    assert decisive in bounded
    spans = json.loads(trace["verifier_input_evidence_spans"])
    assert any(
        span["span_start"] <= long_item["text"].index(decisive)
        and span["span_end"] >= long_item["text"].index(decisive) + len(decisive)
        and bounded.endswith(long_item["text"][span["span_start"] : span["span_end"]])
        for span in spans
    )


def test_boolean_required_slot_preserves_competing_proposition_candidates():
    related = _item(
        "related",
        "Previous work evaluated non-English datasets.",
        section="related_work",
    )
    current = _item(
        "current",
        "We compiled a corpus from topics in English-speaking countries.",
        section="methods",
    )
    prediction = {
        "evidence_metadata": {
            "query_plan": {
                "evidence_slots": [
                    {
                        "slot_id": "support:boolean_proposition",
                        "statement_kind": "boolean_proposition",
                        "required_for_verification": True,
                        "evidence_ids": [
                            "evidence:paper:related",
                            "evidence:paper:current",
                        ],
                    }
                ]
            }
        }
    }

    priorities = qasper_evidence_priorities(
        prediction,
        [related, current],
        question="Do they report results only on English data?",
        candidate_answer="no",
    )

    assert set(priorities.required_evidence_ids) == {
        "evidence:paper:related",
        "evidence:paper:current",
    }

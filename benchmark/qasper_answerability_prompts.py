from __future__ import annotations


def json_structure_repair_prompt(
    response: str,
    *,
    allowed_values: tuple[str, ...],
) -> str:
    values = ", ".join(f'"{value}"' for value in allowed_values)
    return (
        "/no_think\n"
        "Repair only the JSON structure of the verifier response below. "
        "Do not reconsider the evidence, question, candidate, verdict, or "
        "evidence quote. Preserve the original verdict and quote exactly when "
        "they are present. Return one JSON object with exactly the keys "
        '"verdict" and "evidence_quote". The allowed verdict values are: '
        f"{values}.\n\n"
        f"VERIFIER RESPONSE:\n{response}"
    )


def answerability_prompt(
    *,
    question: str,
    evidence: str,
    candidate_answer: str,
) -> str:
    return (
        "/no_think\n"
        "You are a QASPER evidence-sufficiency verifier. Decide whether the "
        "retrieved paper evidence explicitly supports the complete candidate "
        "answer to the question. Topic overlap or a plausible answer is not "
        "sufficient. Every entity, relation, metric, qualifier, polarity, and "
        "number in the candidate must be entailed. For yes/no candidates, the "
        "evidence must support that polarity. Return unsupported when the "
        "paper merely mentions related facts. For a supported verdict, quote "
        "the shortest exact evidence span, at most 20 words, that states the "
        "question-candidate relation. If no such exact span exists, return "
        "unsupported with an empty evidence_quote.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"RETRIEVED PAPER EVIDENCE:\n{evidence}\n\n"
        f"CANDIDATE ANSWER:\n{candidate_answer}\n\n"
        'Return exactly {"verdict":"supported","evidence_quote":"..."} or '
        '{"verdict":"unsupported","evidence_quote":""}.'
    )


def boolean_answerability_prompt(*, question: str, evidence: str) -> str:
    return (
        "/no_think\n"
        "You are a QASPER proposition verifier. Compare the complete yes/no "
        "question proposition with the retrieved paper evidence. A complete "
        "match requires the same subject, relation, object, scope, qualifiers, "
        "and polarity. Distinguish a process from its outcome, mentioning from "
        "performing, creating from experimenting, and controlling experimental "
        "collection from validating the quality of the resulting data.\n\n"
        "Modal relations are strict: evidence that a method can be used, is "
        "compatible, or works as a drop-in component does not prove that it is "
        "required. Conversely, 'without fine-tuning' or 'not required' supports "
        "no for a requirement question.\n\n"
        "Return yes_complete or no_complete only when one polarity of that "
        "complete proposition is explicitly established. Return yes_partial "
        "or no_partial when the evidence supports that polarity only for a "
        "related or incomplete proposition. Return insufficient_evidence when "
        "neither polarity is established. Absence of a statement never proves "
        "no. For complete or partial verdicts, include the shortest exact "
        "contiguous evidence span, at most 60 words, that supports the verdict. "
        "Use an empty evidence_quote only for insufficient_evidence.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"RETRIEVED PAPER EVIDENCE:\n{evidence}\n\n"
        'Return exactly {"verdict":"yes_complete","evidence_quote":"..."}, '
        '{"verdict":"no_complete","evidence_quote":"..."}, '
        '{"verdict":"yes_partial","evidence_quote":"..."}, '
        '{"verdict":"no_partial","evidence_quote":"..."}, or '
        '{"verdict":"insufficient_evidence","evidence_quote":""}.'
    )

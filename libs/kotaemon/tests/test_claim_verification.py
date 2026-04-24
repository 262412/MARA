from kotaemon.base.schema import Document
from kotaemon.indices.qa.claim_verification import (
    ClaimSupportStatus,
    extract_claims,
    revise_or_abstain,
    verify_claims,
)


def test_extract_claims_from_markdown_bullets_and_paragraphs():
    answer = """
    # Summary

    Hello, I can help with that.

    - Revenue increased to 42 million in 2024.
    - The project uses formula E = mc^2.

    This is not legal advice.

    The trial included 128 participants.
    """

    claims = extract_claims(answer)

    assert claims == [
        "Revenue increased to 42 million in 2024.",
        "The project uses formula E = mc^2.",
        "The trial included 128 participants.",
    ]


def test_verify_supported_claim_with_text_overlap():
    result = verify_claims(
        answer="Revenue increased to 42 million in 2024.",
        evidence_texts=["The report says revenue increased to 42 million in 2024."],
    )

    assert result.has_unsupported_claims is False
    assert result.claims[0].status == ClaimSupportStatus.SUPPORTED
    assert result.claims[0].score > 0
    assert "revenue increased" in result.claims[0].best_match.evidence_text.lower()


def test_verify_claim_with_number_and_formula_overlap():
    result = verify_claims(
        answer="The model uses alpha = beta + 2 and reached 95% accuracy.",
        evidence_texts=[
            "Results: alpha = beta + 2. Accuracy was 95 percent on the test set."
        ],
    )

    assert result.claims[0].status == ClaimSupportStatus.SUPPORTED


def test_verify_unsupported_claim():
    result = verify_claims(
        answer="The project launched in 2025.",
        evidence_texts=["The project launched in 2024 after the pilot ended."],
    )

    assert result.has_unsupported_claims is True
    assert result.claims[0].status == ClaimSupportStatus.UNSUPPORTED


def test_revision_removes_unsupported_claims_and_keeps_supported_claims():
    result = verify_claims(
        answer=(
            "Revenue increased to 42 million in 2024. " "The project launched in 2025."
        ),
        evidence_texts=[
            "The report says revenue increased to 42 million in 2024.",
            "The project launched in 2024 after the pilot ended.",
        ],
    )

    revised = revise_or_abstain(result)

    assert "Revenue increased to 42 million in 2024." in revised.text
    assert "The project launched in 2025." not in revised.text
    assert revised.abstained is False
    assert "unsupported claim" in revised.verification_note.lower()


def test_all_unsupported_claims_abstain():
    result = verify_claims(
        answer="The project launched in 2025.",
        evidence_texts=["The project launched in 2024 after the pilot ended."],
    )

    revised = revise_or_abstain(result)

    assert revised.abstained is True
    assert "无法支持" in revised.text


def test_source_document_metadata_is_included_in_match():
    source = Document(
        "Revenue increased to 42 million in 2024.",
        metadata={"filename": "annual-report.pdf", "page": 7},
    )

    result = verify_claims(
        answer="Revenue increased to 42 million in 2024.",
        evidence_texts=[],
        source_documents=[source],
    )

    match = result.claims[0].best_match
    assert match is not None
    assert match.source_metadata == {"filename": "annual-report.pdf", "page": 7}

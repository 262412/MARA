from ktem.pages.chat.chat_docqa_runtime import build_web_docqa_request


def test_web_docqa_request_preserves_phase1_contract_fields():
    page_image_records = [{"evidence_id": "page-image:file-1:3", "page_label": "3"}]

    request = build_web_docqa_request(
        prompt="/no_think What changed?",
        planner_backend="heuristic_local",
        verification_domain="finance",
        page_image_records=page_image_records,
        max_context_length=4096,
    )

    assert request.prompt.startswith("/no_think ")
    assert request.planner_backend == "heuristic_local"
    assert request.verification_domain == "finance"
    assert request.page_image_records == page_image_records
    assert request.max_context_length == 4096

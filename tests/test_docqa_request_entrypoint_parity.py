from __future__ import annotations

from types import SimpleNamespace

from slide_cli.docqa_cli import _run_docqa_turn

from benchmark.engines import DocQARuntimeEngine
from benchmark.schemas import BenchmarkDocument, BenchmarkExample
from kotaemon import cli as legacy_cli


class _RuntimeCapture:
    def __init__(self):
        self.request = None

    def run_turn(self, request):
        self.request = request
        return request


def test_mara_cli_request_uses_named_policy_and_preserves_selection_semantics():
    from ktem.docqa.request_policies import MARA_CLI_REQUEST_POLICY

    runtime = _RuntimeCapture()
    inherited = _run_docqa_turn(runtime, prompt="question", selected_file_ids=None)
    cleared = _run_docqa_turn(runtime, prompt="question", selected_file_ids=[])

    assert inherited.qa_scope == MARA_CLI_REQUEST_POLICY.qa_scope_default == "auto"
    assert inherited.page_number is None
    assert inherited.controller_mode == "off"
    assert inherited.route_policy == "auto"
    assert inherited.verification_mode == "off"
    assert inherited.allowed_routes == []
    assert inherited.origin == "cli"
    assert inherited.selected_file_ids is None
    assert cleared.selected_file_ids == []


def test_legacy_cli_request_keeps_raw_controller_defaults():
    from ktem.docqa.request_policies import LEGACY_CLI_REQUEST_POLICY

    request = legacy_cli._build_legacy_docqa_request(prompt="question")

    assert request.qa_scope == LEGACY_CLI_REQUEST_POLICY.qa_scope_default == "auto"
    assert request.page_number is None
    assert request.controller_mode is None
    assert request.route_policy is None
    assert request.verification_mode is None
    assert request.allowed_routes is None
    assert request.origin == "cli"


def test_benchmark_request_uses_named_policy_and_keeps_benchmark_lists(tmp_path):
    from ktem.docqa.request_policies import BENCHMARK_REQUEST_POLICY

    engine = DocQARuntimeEngine({})
    example = BenchmarkExample(
        example_id="example-1",
        document_id="document-1",
        question="What changed?",
        answers=["Revenue increased."],
        evidence_pages=[7],
        metadata={"dataset_family": "financebench", "page": 7},
    )
    documents = [
        BenchmarkDocument(
            document_id="document-1",
            path=tmp_path / "report.pdf",
            format_type="pdf",
        )
    ]

    kwargs = engine._docqa_request_kwargs(
        example=example,
        documents=documents,
        selected_file_ids=[],
        active_record=SimpleNamespace(file_id="", name=""),
    )

    assert kwargs["qa_scope"] == BENCHMARK_REQUEST_POLICY.qa_scope_default
    assert kwargs["page_number"] == 7
    assert kwargs["origin"] == "benchmark"
    assert kwargs["max_context_length"] == 16000
    assert kwargs["selected_file_ids"] == []
    assert isinstance(kwargs["page_image_records"], list)
    assert isinstance(kwargs["element_index_records"], list)
    assert kwargs["dataset_family"] == "finance"
    assert kwargs["verification_domain"] == "finance"

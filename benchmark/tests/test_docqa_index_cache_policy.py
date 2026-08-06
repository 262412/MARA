from types import SimpleNamespace

from benchmark.docqa_index_cache import (
    qasper_deterministic_index_settings,
    route_requires_element,
)


def test_controller_route_prepares_element_index_when_doc_element_is_allowed():
    config = SimpleNamespace(
        route="controller_auto",
        route_policy="cost_aware",
        allowed_routes=["doc_text", "hybrid", "doc_page_image", "doc_element"],
    )

    assert route_requires_element(config) is True


def test_text_route_does_not_prepare_element_index():
    config = SimpleNamespace(
        route="text_rag",
        route_policy="text",
        allowed_routes=["doc_text"],
    )

    assert route_requires_element(config) is False


def test_qasper_indexing_enables_deterministic_chunk_ids_without_mutating_defaults():
    defaults = {"index.options.1.reader_mode": "default"}
    runtime = SimpleNamespace(
        file_index=SimpleNamespace(id=1),
        load_settings=lambda: defaults,
    )

    settings = qasper_deterministic_index_settings(
        SimpleNamespace(suite_name="qasper-typed159x3"),
        runtime,
    )

    assert settings == {
        "index.options.1.reader_mode": "default",
        "index.options.1.deterministic_chunk_ids": True,
    }
    assert defaults == {"index.options.1.reader_mode": "default"}


def test_non_qasper_indexing_keeps_runtime_default_settings():
    runtime = SimpleNamespace(file_index=SimpleNamespace(id=1))

    assert (
        qasper_deterministic_index_settings(
            SimpleNamespace(suite_name="financebench-20x4"),
            runtime,
        )
        is None
    )

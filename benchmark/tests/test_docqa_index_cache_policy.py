from types import SimpleNamespace

from benchmark.docqa_index_cache import route_requires_element


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

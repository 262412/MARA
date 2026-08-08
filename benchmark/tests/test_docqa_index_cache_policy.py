from types import SimpleNamespace

from benchmark.docqa_index_cache import (
    DocQAIndexCache,
    qasper_deterministic_index_settings,
    route_requires_element,
)
from benchmark.schemas import BenchmarkDocument


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


def test_document_cache_identity_partitions_index_embedding_and_chunk_contracts(
    tmp_path, monkeypatch
):
    path = tmp_path / "paper.txt"
    path.write_text("same document", encoding="utf-8")
    document = BenchmarkDocument("paper", path, format_type="txt")

    def identity(*, index: str, embedding: str, chunk_size: int):
        monkeypatch.setenv("MARA_BENCHMARK_INDEX_CONTRACT", index)
        monkeypatch.setenv("MARA_BENCHMARK_EMBEDDING_CONTRACT", embedding)
        cache = DocQAIndexCache(
            SimpleNamespace(
                suite_name="qasper-typed159x3",
                route="text_rag",
                chunk_size=chunk_size,
                chunk_overlap=64,
            ),
            shared_prepared_file_ids={},
        )
        return cache.document_identity(document)

    first_key, first_trace = identity(
        index="index-v1", embedding="embedding-revision-1", chunk_size=512
    )
    revised_embedding_key, _ = identity(
        index="index-v1", embedding="embedding-revision-2", chunk_size=512
    )
    revised_index_key, _ = identity(
        index="index-v2", embedding="embedding-revision-1", chunk_size=512
    )
    revised_chunk_key, _ = identity(
        index="index-v1", embedding="embedding-revision-1", chunk_size=1024
    )

    assert (
        len({first_key, revised_embedding_key, revised_index_key, revised_chunk_key})
        == 4
    )
    assert first_trace["index_contract"] == "index-v1"
    assert first_trace["embedding_contract"] == "embedding-revision-1"
    assert first_trace["chunking_contract"] == {
        "chunk_size": 512,
        "chunk_overlap": 64,
        "deterministic_chunk_ids": True,
    }

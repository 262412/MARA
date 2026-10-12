"""Local parsing must not trigger the upstream model auto-installer."""

from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("reader", ["general", "pdf_ocr"])
def test_missing_local_model_stops_before_partition(tmp_path, monkeypatch, reader):
    import spacy
    from unstructured.partition import auto

    from kotaemon.loaders import UnstructuredReader
    from kotaemon.loaders.utils.pdf_ocr import read_pdf_unstructured

    def missing(*args, **kwargs):
        raise OSError("No installed model")

    def unexpected(*args, **kwargs):
        pytest.fail("Partition must not reach its automatic model installer")

    monkeypatch.setattr(spacy, "load", missing)
    monkeypatch.setattr(auto, "partition", unexpected)
    with pytest.raises(RuntimeError, match="en_core_web_sm.*locally"):
        if reader == "general":
            UnstructuredReader().load_data(tmp_path / "sample.txt")
        else:
            read_pdf_unstructured(tmp_path / "sample.pdf")


def test_local_model_preserves_partition_output(tmp_path, monkeypatch):
    import spacy
    from unstructured.partition import auto

    from kotaemon.loaders import UnstructuredReader

    loads = []
    monkeypatch.setattr(spacy, "load", lambda name, **kwargs: loads.append(name))
    monkeypatch.setattr(
        auto,
        "partition",
        lambda **kwargs: [
            SimpleNamespace(
                text="local parsed text", metadata=SimpleNamespace(page_number=2)
            )
        ],
    )
    documents = UnstructuredReader().load_data(
        tmp_path / "sample.txt", split_documents=True
    )
    assert loads == ["en_core_web_sm"]
    assert documents[0].text == "local parsed text"
    assert documents[0].metadata["page_number"] == 2

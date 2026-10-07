"""Keep the NLTK upgrade compatible with MARA's offline text paths."""

import json
import os
import pickle
import socket
from io import BytesIO

import nltk
import pytest
from nltk.tokenize import PunktSentenceTokenizer, TreebankWordTokenizer
from nltk.tokenize.punkt import PunktParameters, punkt_pickle_load, save_punkt_params


@pytest.fixture
def offline_nltk(monkeypatch, tmp_path):
    def unexpected_network(*args, **kwargs):
        raise AssertionError("NLTK compatibility tests must use fixed local resources")

    monkeypatch.setattr(nltk, "download", unexpected_network)
    monkeypatch.setattr(socket, "create_connection", unexpected_network)
    monkeypatch.setattr(socket.socket, "connect", unexpected_network)
    data = tmp_path / "nltk_data"
    punkt = data / "tokenizers/punkt_tab/english"
    punkt.mkdir(parents=True)
    save_punkt_params(PunktParameters(), dir=str(punkt))
    (data / "tokenizers/punkt").mkdir()
    stopwords = data / "corpora/stopwords"
    stopwords.mkdir(parents=True)
    (stopwords / "english").write_text("the\nand\n", encoding="utf-8")
    tagger = data / "taggers/averaged_perceptron_tagger_eng"
    tagger.mkdir(parents=True)
    for name, value in {"weights": {}, "tagdict": {}, "classes": ["NN"]}.items():
        (tagger / f"averaged_perceptron_tagger_eng.{name}.json").write_text(
            json.dumps(value), encoding="utf-8"
        )
    monkeypatch.setenv("NLTK_DATA", str(data))
    monkeypatch.setattr(nltk.data, "path", [str(data)])
    nltk.tokenize._get_punkt_tokenizer.cache_clear()
    yield data
    nltk.tokenize._get_punkt_tokenizer.cache_clear()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("Alpha beta. Gamma delta!", ["Alpha beta.", "Gamma delta!"]),
        (
            "A price of 3.14 is stable.\nNext line.",
            ["A price of 3.14 is stable.", "Next line."],
        ),
    ],
)
def test_sentence_tokenization_keeps_fixed_output(offline_nltk, text, expected):
    assert PunktSentenceTokenizer().tokenize(text) == expected
    assert nltk.sent_tokenize(text) == expected


def test_word_tokenization_keeps_contractions_and_punctuation(offline_nltk):
    expected = ["Alpha", "is", "n't", "beta", "."]
    assert TreebankWordTokenizer().tokenize("Alpha isn't beta.") == expected
    assert nltk.word_tokenize("Alpha isn't beta.") == expected


def test_unstructured_uses_the_same_fixed_local_resources(offline_nltk):
    from unstructured.nlp.tokenize import sent_tokenize, word_tokenize

    sent_tokenize.cache_clear()
    word_tokenize.cache_clear()
    assert sent_tokenize("Alpha beta. Gamma delta!") == ["Alpha beta.", "Gamma delta!"]
    assert word_tokenize("Alpha isn't beta.") == ["Alpha", "is", "n't", "beta", "."]


def test_sentence_window_preserves_indexing_metadata(offline_nltk):
    from llama_index.core.node_parser import SentenceWindowNodeParser
    from llama_index.core.schema import NodeRelationship

    from kotaemon.base import Document

    document = Document(
        content="Alpha beta. Gamma delta! Final line?",
        id_="nltk-fixed-document",
        metadata={"file_name": "fixed.txt"},
    )
    # This is the NLTK-backed parser used by MARA's SentenceWindowSplitter.
    parser = SentenceWindowNodeParser.from_defaults(window_size=1)
    chunks = parser.get_nodes_from_documents([document])
    assert [chunk.text for chunk in chunks] == [
        "Alpha beta. ",
        "Gamma delta! ",
        "Final line?",
    ]
    assert [chunk.metadata["window"] for chunk in chunks] == [
        "Alpha beta.  Gamma delta! ",
        "Alpha beta.  Gamma delta!  Final line?",
        "Gamma delta!  Final line?",
    ]
    for chunk in chunks:
        assert chunk.metadata["original_text"] == chunk.text
        assert chunk.metadata["file_name"] == "fixed.txt"
        assert chunk.relationships[NodeRelationship.SOURCE].node_id == document.doc_id
        assert "window" in chunk.excluded_embed_metadata_keys
        assert "original_text" in chunk.excluded_llm_metadata_keys


@pytest.mark.parametrize("multiple", [False, True])
def test_resource_search_keeps_order_and_readonly_contents(
    offline_nltk, tmp_path, monkeypatch, multiple
):
    first, second = tmp_path / "first", tmp_path / "second"
    for directory, text in ((first, "first resource"), (second, "second resource")):
        directory.mkdir()
        resource = directory / "fixed.txt"
        resource.write_text(text, encoding="utf-8")
        resource.chmod(0o444)
    paths = [str(first), str(second)] if multiple else [str(first)]
    monkeypatch.setenv("NLTK_DATA", os.pathsep.join(paths))
    monkeypatch.setattr(nltk.data, "path", paths)
    with nltk.data.find("fixed.txt").open() as handle:
        assert handle.read() == b"first resource"
    assert (first / "fixed.txt").read_text(encoding="utf-8") == "first resource"
    assert (second / "fixed.txt").read_text(encoding="utf-8") == "second resource"


def test_legacy_punkt_roundtrip_keeps_sentence_output(offline_nltk):
    tokenizer = PunktSentenceTokenizer()
    loaded = punkt_pickle_load(BytesIO(pickle.dumps(tokenizer)))
    assert loaded.tokenize("Alpha beta. Gamma delta!") == [
        "Alpha beta.",
        "Gamma delta!",
    ]


def test_legacy_punkt_rejects_unrelated_namespace_object(offline_nltk):
    # GLOBAL + STOP resolves a class only: no REDUCE, constructor, or command runs.
    payload = b"cnltk.tokenize.repp\nReppTokenizer\n."
    with pytest.raises(pickle.UnpicklingError):
        punkt_pickle_load(BytesIO(payload))

from pathlib import Path

from kotaemon.base import Document
from kotaemon.indices.parse_cache import load_data_with_parse_cache
from kotaemon.indices.vision_cache import cached_model_result
from kotaemon.loaders import mathpix_loader, ocr_loader
from kotaemon.loaders.utils import adobe


class _FakeLoader:
    parser_version = "v1"

    def __init__(self):
        self.calls = 0

    def load_data(self, file_path, extra_info=None):
        self.calls += 1
        metadata = {
            "loader_call": self.calls,
            "path_obj": Path(file_path),
            **(extra_info or {}),
        }
        return [Document(text=f"parsed-{self.calls}", id_="doc-1", metadata=metadata)]


def test_parse_cache_reuses_file_hash_and_reapplies_runtime_metadata(tmp_path):
    input_file = tmp_path / "input.txt"
    input_file.write_text("same content", encoding="utf-8")
    loader = _FakeLoader()

    first = load_data_with_parse_cache(
        loader,
        input_file,
        extra_info={"file_id": "source-1", "file_name": "input.txt"},
        cache_dir=tmp_path / "parse-cache",
        reader_policy={"reader_mode": "default"},
    )
    second = load_data_with_parse_cache(
        loader,
        input_file,
        extra_info={"file_id": "source-2", "file_name": "input.txt"},
        cache_dir=tmp_path / "parse-cache",
        reader_policy={"reader_mode": "default"},
    )

    assert loader.calls == 1
    assert first.cache_hit is False
    assert first.stats == {"hits": 0, "misses": 1, "writes": 1}
    assert second.cache_hit is True
    assert second.stats == {"hits": 1, "misses": 0, "writes": 0}
    assert second.documents[0].text == "parsed-1"
    assert second.documents[0].doc_id == "doc-1"
    assert second.documents[0].metadata["file_id"] == "source-2"
    assert second.documents[0].metadata["path_obj"] == str(input_file)

    input_file.write_text("changed content", encoding="utf-8")
    third = load_data_with_parse_cache(
        loader,
        input_file,
        extra_info={"file_id": "source-3", "file_name": "input.txt"},
        cache_dir=tmp_path / "parse-cache",
        reader_policy={"reader_mode": "default"},
    )

    assert loader.calls == 2
    assert third.cache_hit is False
    assert third.documents[0].text == "parsed-2"


def test_cached_model_result_reuses_vlm_and_ocr_outputs(tmp_path):
    calls = 0

    def compute():
        nonlocal calls
        calls += 1
        return {"caption": "chart summary"}

    first = cached_model_result(
        cache_dir=tmp_path,
        namespace="vlm",
        payload="data:image/png;base64,AAA",
        model_name="vision-model",
        compute=compute,
    )
    second = cached_model_result(
        cache_dir=tmp_path,
        namespace="vlm",
        payload="data:image/png;base64,AAA",
        model_name="vision-model",
        compute=compute,
    )

    assert calls == 1
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.value == {"caption": "chart summary"}
    assert second.stats == {"hits": 1, "misses": 0, "writes": 0}


def test_generate_single_figure_caption_uses_configured_cache(tmp_path, monkeypatch):
    calls = 0

    def fake_generate_gpt4v(endpoint, prompt, images):
        nonlocal calls
        calls += 1
        return f"{endpoint}:{images}:caption"

    monkeypatch.setattr(adobe.flowsettings, "KH_VISION_CACHE_DIR", tmp_path)
    monkeypatch.setattr(adobe, "generate_gpt4v", fake_generate_gpt4v)

    first = adobe.generate_single_figure_caption("vlm-endpoint", "figure-bytes")
    second = adobe.generate_single_figure_caption("vlm-endpoint", "figure-bytes")

    assert first == "vlm-endpoint:figure-bytes:caption"
    assert second == first
    assert calls == 1


def test_ocr_reader_caches_external_ocr_response(tmp_path, monkeypatch):
    input_file = tmp_path / "input.pdf"
    input_file.write_bytes(b"%PDF-1.4")
    calls = 0

    class _Response:
        def json(self):
            return {"result": [{"csv_string": "ocr text"}]}

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _Response()

    monkeypatch.setattr(ocr_loader.flowsettings, "KH_OCR_CACHE_DIR", tmp_path / "ocr")
    monkeypatch.setattr(ocr_loader, "tenacious_api_post", fake_post)
    monkeypatch.setattr(ocr_loader, "read_pdf_unstructured", lambda _path: [])
    monkeypatch.setattr(
        ocr_loader,
        "parse_ocr_output",
        lambda _ocr, _pdf, **_kwargs: ([], [(0, "ocr text")]),
    )

    reader = ocr_loader.OCRReader(endpoint="ocr-model")
    first = reader.load_data(input_file)
    second = reader.load_data(input_file)

    assert calls == 1
    assert first[0].text == "ocr text"
    assert second[0].text == "ocr text"
    assert reader.last_ocr_cache_stats == {"hits": 1, "misses": 0, "writes": 0}


def test_mathpix_reader_caches_processed_formula_output(tmp_path, monkeypatch):
    input_file = tmp_path / "formula.pdf"
    input_file.write_bytes(b"%PDF-1.4 formula")
    calls = 0

    def fake_send_pdf(_path):
        return "pdf-id"

    def fake_get_processed_pdf(_pdf_id):
        nonlocal calls
        calls += 1
        return "# Page 1\nE = mc^2"

    monkeypatch.setattr(
        mathpix_loader.flowsettings, "KH_FORMULA_OCR_CACHE_DIR", tmp_path / "formula"
    )

    reader = mathpix_loader.MathpixPDFReader(should_clean_pdf=False)
    monkeypatch.setattr(reader, "send_pdf", fake_send_pdf)
    monkeypatch.setattr(reader, "get_processed_pdf", fake_get_processed_pdf)

    first = reader.load_data(input_file)
    second = reader.load_data(input_file)

    assert calls == 1
    assert first[0].text == "E = mc^2"
    assert second[0].text == "E = mc^2"
    assert reader.last_formula_ocr_cache_stats == {
        "hits": 1,
        "misses": 0,
        "writes": 0,
    }

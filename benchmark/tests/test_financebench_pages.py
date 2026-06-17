from benchmark import financebench_pages
from benchmark.financebench_pages import align_financebench_page


def test_align_financebench_page_reuses_extracted_pdf_pages(monkeypatch, tmp_path):
    calls = []
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")

    def fake_extract(path, *, page_numbers=None):
        calls.append(path)
        return [(1, "Cover"), (5, "Revenue was 10.")]

    monkeypatch.setattr(financebench_pages, "extract_pdf_pages", fake_extract)

    assert align_financebench_page(pdf_path, 4, "Revenue was 10.") == (
        5,
        "financebench_span_to_parser_page",
    )
    assert align_financebench_page(pdf_path, 4, "Revenue was 10.") == (
        5,
        "financebench_span_to_parser_page",
    )
    assert calls == [pdf_path]


def test_align_financebench_page_extracts_only_candidate_parser_pages(
    monkeypatch, tmp_path
):
    requested_page_windows = []
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")

    def fake_extract(_path, *, page_numbers=None):
        requested_page_windows.append(tuple(page_numbers or ()))
        return [(5, "Revenue was 10.")]

    monkeypatch.setattr(financebench_pages, "extract_pdf_pages", fake_extract)

    assert align_financebench_page(pdf_path, 4, "Revenue was 10.") == (
        5,
        "financebench_span_to_parser_page",
    )
    assert requested_page_windows == [(2, 3, 4, 5, 6)]

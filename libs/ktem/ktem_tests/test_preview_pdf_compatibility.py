from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlsplit


def test_legacy_pdf_page_helpers_keep_clamp_and_failure_fallback(tmp_path):
    from ktem.pages.chat.page_preview_runtime import clamp_page, safe_pdf_page_count

    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"not a pdf")

    assert clamp_page(0, 4) == 1
    assert clamp_page(99, 4) == 4
    assert safe_pdf_page_count(str(corrupt), fallback=7) == 7


def test_pdfjs_viewer_query_hash_and_ktemfit_contract(monkeypatch, tmp_path):
    from ktem.pages.chat import page_preview_runtime

    app_data = tmp_path / "app-data"
    viewer = app_data / "assets" / "pdfjs" / "6.1.200" / "web" / "viewer.html"
    viewer.parent.mkdir(parents=True)
    viewer.write_text("viewer", encoding="utf-8")
    monkeypatch.setattr(
        page_preview_runtime,
        "get_pdfjs_runtime_dir",
        lambda _app_data: viewer.parents[1],
    )

    source = "/tmp/report name.pdf"
    pdf_url = page_preview_runtime.build_pdfjs_viewer_src(source, 3, "pdf")
    office_url = page_preview_runtime.build_pdfjs_viewer_src(source, 3, "office")

    for url, fit_mode in ((pdf_url, "pdf"), (office_url, "office")):
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        assert parsed.fragment == "page=3"
        assert query["embed"] == ["1"]
        assert query["disablehistory"] == ["true"]
        assert query["sidebarviewonload"] == ["0"]
        assert query["ktempage"] == ["3"]
        assert query["ktemv"] == ["12"]
        assert query["ktemfit"] == [fit_mode]
        assert unquote(query["file"][0]).endswith("/file=/tmp/report name.pdf")

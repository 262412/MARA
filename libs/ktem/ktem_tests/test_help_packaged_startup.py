from unittest.mock import Mock

import pytest
import requests
from ktem.pages import help as help_page


def test_packaged_help_uses_bundled_markdown_when_user_docs_are_absent(
    monkeypatch, tmp_path
):
    request = Mock(side_effect=AssertionError("network request during packaged help"))
    monkeypatch.setattr(help_page.requests, "get", request)
    page = object.__new__(help_page.HelpPage)
    page.doc_dir = tmp_path / "missing-docs"
    page.remote_content_url = "https://example.test/docs"
    page.app_version = "0.0.41"

    assert page._load_doc_markdown("usage.md").strip()
    request.assert_not_called()


def test_disabled_remote_help_does_not_contact_external_services(monkeypatch):
    monkeypatch.setattr(help_page, "ALLOW_REMOTE_HELP", False, raising=False)
    request = Mock(side_effect=AssertionError("unexpected network request"))
    monkeypatch.setattr(help_page.requests, "get", request)

    assert help_page.get_remote_doc("https://example.test/help") == ""
    assert help_page.download_changelogs("https://example.test/release") == ""
    request.assert_not_called()


@pytest.mark.parametrize("loader", ["get_remote_doc", "download_changelogs"])
def test_optional_remote_help_has_a_bounded_timeout(monkeypatch, loader):
    monkeypatch.setattr(help_page, "ALLOW_REMOTE_HELP", True, raising=False)
    request = Mock(side_effect=requests.Timeout("offline"))
    monkeypatch.setattr(help_page.requests, "get", request)

    assert getattr(help_page, loader)("https://example.test/help") == ""
    assert request.call_args.kwargs["timeout"] == (3, 5)


def test_changelog_download_returns_release_body_with_a_bounded_request(monkeypatch):
    monkeypatch.setattr(help_page, "ALLOW_REMOTE_HELP", True)
    response = Mock()
    response.json.return_value = {"body": "Release notes"}
    request = Mock(return_value=response)
    monkeypatch.setattr(help_page.requests, "get", request)

    assert (
        help_page.download_changelogs("https://example.test/release") == "Release notes"
    )
    request.assert_called_once_with("https://example.test/release", timeout=(3, 5))
    response.raise_for_status.assert_called_once_with()


def test_changelog_download_rejects_http_errors_before_reading_json(monkeypatch):
    monkeypatch.setattr(help_page, "ALLOW_REMOTE_HELP", True)
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError("HTTP 503")
    monkeypatch.setattr(help_page.requests, "get", Mock(return_value=response))

    assert help_page.download_changelogs("https://example.test/release") == ""
    response.json.assert_not_called()


def test_changelog_cache_uses_the_application_version(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    (tmp_path / "0.0.41.md").write_text("Cached release notes", encoding="utf-8")
    download = Mock(return_value="")
    monkeypatch.setattr(help_page, "download_changelogs", download)
    monkeypatch.setattr(help_page.HelpPage, "_load_doc_markdown", lambda *_: "")
    monkeypatch.setattr(help_page.gr, "Accordion", MagicMock())
    monkeypatch.setattr(help_page.gr, "Markdown", Mock())

    help_page.HelpPage(
        None, doc_dir=str(tmp_path), app_version="0.0.41", changelogs_cache_dir=tmp_path
    )

    download.assert_not_called()

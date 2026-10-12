import pytest

from scripts.check_nltk_backport import check_advisories


@pytest.mark.parametrize(
    "report",
    [{"error": "upstream unavailable"}, None, [], {"vulns": None}, {"vulns": [{}]}],
)
def test_advisory_gate_rejects_malformed_responses(report):
    with pytest.raises(ValueError, match="Invalid OSV"):
        check_advisories(report)


def test_advisory_gate_rejects_new_base_vulnerabilities():
    with pytest.raises(ValueError, match="GHSA-new-finding"):
        check_advisories({"vulns": [{"id": "GHSA-new-finding"}]})


def test_advisory_gate_accepts_only_the_remediated_finding():
    check_advisories({})
    check_advisories(
        {"vulns": [{"id": "GHSA-8mgp-746c-j5xp", "aliases": ["CVE-2026-81726"]}]}
    )


def test_upstream_runner_isolates_tests_installed_below_a_project(
    monkeypatch, tmp_path
):
    from types import SimpleNamespace

    from scripts import check_nltk_backport as gate

    project = tmp_path / "project"
    package = project / ".venv/site-packages"
    tests = package / "nltk/test/unit"
    tests.mkdir(parents=True)
    (project / "conftest.py").write_text(
        "raise RuntimeError('unrelated parent conftest was imported')\n",
        encoding="utf-8",
    )
    for name in gate.TESTS:
        (tests / name).write_text(
            "import nltk, pytest\n"
            "def test_downloads_remain_blocked():\n"
            "    with pytest.raises(RuntimeError, match='disabled'):\n"
            "        nltk.download('untrusted-fixture')\n",
            encoding="utf-8",
        )
    monkeypatch.setenv("MARA_PYTEST_RUNTIME_PARENT", str(tmp_path / "owned"))
    monkeypatch.setattr(gate, "_test_resources", lambda root, archive: root / "cache")
    distribution = SimpleNamespace(locate_file=lambda name: package / name)
    assert gate._run_upstream_tests(distribution, None) == 0

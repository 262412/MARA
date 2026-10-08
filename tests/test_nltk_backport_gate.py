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

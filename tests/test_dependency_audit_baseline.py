from __future__ import annotations

from scripts.check_dependency_audit import compare_audit_report


def _report(*finding_ids: str, statuses: tuple[str, ...] = ()) -> dict:
    return {
        "vulnerabilities": [
            {
                "dependency": {"name": "demo", "version": "1.0"},
                "id": finding_id,
            }
            for finding_id in finding_ids
        ],
        "adverse_statuses": [
            {"name": status.split("|", 1)[0], "status": status.split("|", 1)[1]}
            for status in statuses
        ],
    }


def test_dependency_audit_accepts_known_findings_and_resolved_entries():
    baseline = {
        "known_findings": ["demo==1.0|CVE-1", "demo==1.0|CVE-2"],
        "known_adverse_statuses": ["archived-demo|archived"],
    }

    result = compare_audit_report(_report("CVE-1"), baseline)

    assert result.new_findings == ()
    assert result.resolved_findings == ("demo==1.0|CVE-2",)
    assert result.new_adverse_statuses == ()


def test_dependency_audit_rejects_new_findings_and_statuses():
    baseline = {
        "known_findings": ["demo==1.0|CVE-1"],
        "known_adverse_statuses": [],
    }

    result = compare_audit_report(
        _report("CVE-1", "CVE-NEW", statuses=("demo|archived",)),
        baseline,
    )

    assert result.new_findings == ("demo==1.0|CVE-NEW",)
    assert result.new_adverse_statuses == ("demo|archived",)

from __future__ import annotations

import pytest

from scripts.check_dependency_audit import (
    compare_audit_report,
    filter_report_to_active_versions,
)


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


def test_dependency_audit_filters_inactive_universal_lock_versions():
    report = {
        "vulnerabilities": [
            {
                "dependency": {"name": "demo_package", "version": version},
                "id": finding_id,
            }
            for version, finding_id in (("1.0", "CVE-OLD"), ("2.0", "CVE-ACTIVE"))
        ],
        "adverse_statuses": [],
    }

    filtered = filter_report_to_active_versions(report, {"demo-package==2.0"})

    assert [item["id"] for item in filtered["vulnerabilities"]] == ["CVE-ACTIVE"]


def test_dependency_audit_fails_closed_when_tree_omits_audited_package():
    with pytest.raises(ValueError, match="absent from the active dependency tree"):
        filter_report_to_active_versions(_report("CVE-NEW"), {"other==1.0"})

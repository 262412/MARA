from __future__ import annotations

from types import SimpleNamespace

from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan
from ktem.docqa.visual_time_series import visual_time_series_authority


def test_verified_year_series_answers_the_requested_trend_without_value_dump() -> None:
    request, bundle = _time_series_request_and_bundle()

    authority = visual_time_series_authority(request, bundle)

    assert authority is not None
    assert authority["answer"] == (
        "Total Shareholder Return peaked in 2018, then declined in subsequent "
        "years, reaching a low in 2020 before increasing in 2021."
    )


def test_incomplete_year_series_has_no_visual_time_series_authority() -> None:
    request, bundle = _time_series_request_and_bundle()
    incomplete = EvidenceBundle(route=bundle.route, items=bundle.items[:-1])

    authority = visual_time_series_authority(request, incomplete)

    assert authority is None


def _time_series_request_and_bundle() -> tuple[SimpleNamespace, EvidenceBundle]:
    values = {
        "2017": "1082.4",
        "2018": "1200.0",
        "2019": "1186.7",
        "2020": "810.8",
        "2021": "921.0",
    }
    items = [_cell(period, value) for period, value in values.items()]
    slots = tuple(
        EvidenceSlot(
            slot_id=f"support:{period}",
            role="support",
            metric="Total Shareholder Return",
            period=period,
            modality="table",
            required_for_verification=True,
            statement_kind="visual_time_series_cell",
            status="filled",
            evidence_ids=(identity_of(item).key,),
        )
        for period, item in zip(values, items)
    )
    plan = QueryPlan(
        answer_type="free_text",
        question_type="visual_time_series",
        plan_id="plan:visual-time-series",
        evidence_slots=slots,
    )
    return (
        SimpleNamespace(query_plan=plan, query_plan_state_version=1),
        EvidenceBundle(route="element_rag", items=items),
    )


def _cell(period: str, value: str) -> dict[str, object]:
    return {
        "source_id": "report",
        "evidence_id": f"return:{period}",
        "page_label": "35",
        "table_id": "shareholder-return",
        "cell_id": f"return:{period}",
        "evidence_level": "cell",
        "modality": "table",
        "row_label": "Total Shareholder Return",
        "period": period,
        "value": value,
        "text": f"Total Shareholder Return {period} {value}",
        "metadata": {"visual_extraction_source": "table_parser"},
    }

"""Audit saved observations without importing LMDoc or calling any provider."""

import copy
import gzip
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


def read(path):
    source = ROOT / path
    if source.exists():
        return json.loads(source.read_text(encoding="utf8"))
    with gzip.open(
        source.with_suffix(source.suffix + ".gz"), "rt", encoding="utf8"
    ) as stream:
        return json.load(stream)


def percent(text):
    match = re.search(r"-\d+(?:\.\d+)?\s*%", text)
    assert match, "No negative percentage in captured answer"
    return float(match.group().replace("%", "").strip())


def verify_harbor():
    report = {"policy_returns": 0, "guide_abstentions": 0}
    for repeat in range(1, 6):
        before = read(f"harbor/{repeat:02d}-before-response.json")
        after = read(f"harbor/{repeat:02d}-after-response.json")
        a = read(f"harbor/{repeat:02d}-before-request.json")
        b = read(f"harbor/{repeat:02d}-after-request.json")
        assert [key for key in a if a[key] != b[key]] == ["selected_file_ids"]
        assert before["settings"] == after["settings"]
        assert before["guardrail_decision"]["action"] == "abstain"
        assert after["guardrail_decision"]["action"] == "return"
        assert after["verify_decision"]["status"] == "supported"
        assert "17 days" in after["answer"]
        for label in ("before", "after"):
            calls = read(f"harbor/{repeat:02d}-{label}-provider-calls.json")
            assert calls and all(call["complete"] for call in calls)
        report["guide_abstentions"] += 1
        report["policy_returns"] += 1
    return report


def verify_replay():
    report: dict[str, Any] = {}
    old = read("unpatched-claim-replay.json")
    new = read("patched-claim-replay.json")
    assert old[0]["claims"] == new[0]["claims"]
    assert old[0]["replayed_status"] == "unsupported"
    assert new[0]["replayed_status"] == "supported"
    report["old_verifier_accepts_new_policy_claims"] = sum(
        row["replayed_status"] == "supported"
        for row in old
        if row["label"].endswith("-after")
    )
    diagnostic = read("installed-verifier.json")
    failing = next(
        check
        for item in diagnostic["details"]
        for check in item["evidence_checks"]
        if not check["support"]
    )
    total = len(failing["claim_tokens"])
    report["lexical_check"] = {
        "matched": total - len(failing["missing_tokens"]),
        "total": total,
        "required": math.ceil(total * 0.75),
    }
    test_result = re.search(r"(\d+) passed", (ROOT / "verifier-suite.log").read_text())
    assert test_result is not None
    report["subsystem_tests_passed"] = int(test_result.group(1))
    return report


def verify_chart(folder="visual"):
    report: dict[str, Any] = {}
    auto = read(f"{folder}/automatic-response.json")
    visual = read(f"{folder}/fixed-visual-response.json")
    a = read(f"{folder}/automatic-request.json")
    b = read(f"{folder}/fixed-visual-request.json")
    assert [key for key in a if a[key] != b[key]] == ["route_policy"]
    assert a["verification_mode"] == b["verification_mode"] == "off"
    assert auto["route_decision"]["route"] == "doc_text"
    assert visual["route_decision"]["route"] == "doc_page_image"
    assert not read(f"{folder}/automatic-visual-calls.json")
    calls = read(f"{folder}/fixed-visual-visual-calls.json")
    assert len(calls) == 1
    call = calls[0]
    assert (
        call["request"]["model"]
        == call["response"]["model"]
        == "gpt-4.1-mini-2025-04-14"
    )
    image_parts = [
        part
        for message in call["request"]["messages"]
        for part in message["content"]
        if part["type"] == "image_url"
    ]
    assert len(image_parts) == 1
    image = image_parts[0]["image_url"]["url"]
    data = (ROOT / folder / image["relative_file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == image["sha256"]
    assert data == (ROOT / "visual/input-page9.png").read_bytes()
    expected = copy.deepcopy(call["request"])
    for message in expected["messages"]:
        message["content"] = [
            part for part in message["content"] if part["type"] != "image_url"
        ]
    ablation = read(f"{folder}/image-removed-ablation.json")
    assert ablation["request"] == expected
    value = percent(visual["answer"])
    low, high = read("visual/protocol.json")["reference_percent"]["pink_curve"]
    assert low <= value <= high
    report["visual"] = {
        "automatic_answer_percent": percent(auto["answer"]),
        "fixed_visual_answer_percent": value,
        "image_removed_answer_percent": percent(
            ablation["response"]["choices"][0]["message"]["content"]
        ),
        "reference_low": low,
        "reference_high": high,
        "image_parts": len(image_parts),
        "manual_route_change": True,
    }
    failed = read("preliminary-slot-failure/automatic-response.json")
    assert failed["guardrail_decision"]["action"] == "abstain"
    assert failed["route_decision"]["route"] == "doc_page_image"
    assert not read("preliminary-slot-failure/automatic-visual-calls.json")
    report["preliminary_slot_failure_retained"] = True
    return report


def verify():
    manifest = read("manifest.json")["sha256"]
    for name, expected in manifest.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    assert len(list(ROOT.rglob("*.db"))) == 0
    report: dict[str, Any] = {"files_verified": len(manifest)}
    report.update(verify_harbor())
    report.update(verify_replay())
    report.update(verify_chart())
    report["recipe_validation"] = verify_chart("recipe_validation")["visual"]
    report["historical_slidevqa_outputs_recovered"] = False
    return report


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))

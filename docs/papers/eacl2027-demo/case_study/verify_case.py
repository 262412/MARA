"""Verify the captured case without model access or third-party dependencies."""

import argparse
import hashlib
import json
import re
import string
from collections import Counter
from pathlib import Path


def read_json(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def normalize(answer):
    answer = re.sub(r"【\d+】", "", answer.lower())
    answer = answer.translate(str.maketrans("", "", string.punctuation))
    answer = re.sub(r"\b(a|an|the)\b", " ", answer)
    return " ".join(answer.split())


def score(answer, reference):
    predicted, expected = normalize(answer), normalize(reference)
    tokens, gold = predicted.split(), expected.split()
    overlap = sum((Counter(tokens) & Counter(gold)).values())
    f1 = 2 * overlap / (len(tokens) + len(gold)) if tokens or gold else 1.0
    return {"exact_match": int(predicted == expected), "token_f1": f1}


def check_hashes(root):
    manifest = read_json(root, "manifest.json")
    for name, expected in manifest["sha256"].items():
        digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError(f"File hash mismatch: {name}")
    return len(manifest["sha256"])


def check_turn(root, label, protocol, answers):
    response = read_json(root, f"records/{label}-response.json")
    calls = read_json(root, f"records/{label}-provider-calls.json")
    assert len(calls) == 1 and calls[0]["complete"]
    assert calls[0]["method"] == "stream"
    assert calls[0]["configured_model"] == "deepseek-v4-flash"
    assert response["route_decision"]["route"] == "doc_text"
    assert response["retrieve_decision"]["status"] == "good"
    assert all(not row.get("route_switch_used") for row in response["controller_trace"])
    assert answers["answer_for_user"] == response["answer"]
    assert answers["answer_for_scoring"] == response["answer"]
    assert answers["raw_provider_text"] == [call["text"] for call in calls]
    metadata = response["evidence_bundle"]["metadata"]
    for field in ("pre_verification_answer", "pre_guardrail_answer"):
        assert answers[field] == metadata[field]
    source_name = (
        "harbor-operations.txt" if label == "before" else "harbor-data-policy.txt"
    )
    assert len(response["evidence_bundle"]["items"]) == 1
    item = response["evidence_bundle"]["items"][0]
    assert item["source_name"] == source_name
    source = (root / "inputs" / source_name).read_text(encoding="utf-8").strip()
    assert item["text"].strip() == source
    # The production evidence formatter flattens document line breaks.
    source_words = " ".join(source.split())
    assert any(
        source_words in " ".join(message.get("content", "").split())
        for message in calls[0]["messages"]
    )
    return response, score(answers["answer_for_scoring"], protocol["reference_answer"])


def verify(root):
    checked = check_hashes(root)
    protocol = read_json(root, "case-protocol.json")
    stages = read_json(root, "records/answer-stages.json")
    before, a_score = check_turn(root, "before", protocol, stages["before"])
    after, b_score = check_turn(root, "after", protocol, stages["after"])
    a = read_json(root, "records/before-request.json")
    b = read_json(root, "records/after-request.json")
    assert [key for key in a if a[key] != b[key]] == ["selected_file_ids"]
    assert before["settings"] == after["settings"]
    assert before["conversation_id"] != after["conversation_id"]
    assert before["verify_decision"]["status"] == "unknown"
    assert before["guardrail_decision"]["action"] == "abstain"
    assert after["verify_decision"]["status"] == "supported"
    assert after["guardrail_decision"]["action"] == "return"
    assert "17 days" in after["answer"]
    assert stages["before"]["pre_guardrail_answer"] != before["answer"]
    calculated = {"before": a_score, "after": b_score}
    assert calculated == read_json(root, "records/recomputed-metrics.json")
    repeated = read_json(root, "repeat/after-response.json")
    assert repeated["retrieve_decision"]["status"] == "good"
    assert repeated["verify_decision"]["status"] == "unsupported"
    assert repeated["guardrail_decision"]["action"] == "abstain"
    return {
        "status": "passed",
        "files_checked": checked,
        "metrics": calculated,
        "independent_repeat": "correct-source turn abstained; retained",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    print(json.dumps(verify(args.root.resolve()), indent=2))

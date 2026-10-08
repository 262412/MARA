"""Re-run the verifier on identical captured claims, without model calls."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.source:
        source = args.source.resolve()
        sys.path[:0] = [
            str(source / "libs" / name) for name in ("ktem", "kotaemon", "slide_cli")
        ]
    from ktem.docqa._runtime_models import DocQARequest
    from ktem.docqa.controller import RetrieveDecision
    from ktem.docqa.evidence import EvidenceBundle
    from ktem.docqa.verification import verify_decision

    pairs = [("original-repeat", ROOT.parent / "case_study/repeat/after-response.json")]
    pairs += [
        (p.stem.replace("-response", ""), p)
        for p in sorted((ROOT / "harbor").glob("*-response.json"))
    ]
    rows = []
    for label, path in pairs:
        response = json.loads(path.read_text(encoding="utf8"))
        request_path = path.with_name(path.name.replace("-response", "-request"))
        request = json.loads(request_path.read_text(encoding="utf8"))
        claims = response["verify_decision"]["claims"]
        bundle = EvidenceBundle(
            route="doc_text", items=response["evidence_bundle"]["items"]
        )
        decision = verify_decision(
            DocQARequest(**request),
            RetrieveDecision(status="good", reason="Captured retrieval"),
            bundle,
            "\n".join(claims),
        )
        rows.append({"label": label, "claims": claims, "status": decision.status})
    print(json.dumps(rows, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

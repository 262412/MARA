from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any


def with_default_evidence_ref(response: str) -> str:
    try:
        payload = json.loads(response)
    except (TypeError, json.JSONDecodeError):
        return response
    if (
        isinstance(payload, dict)
        and payload.get("verdict")
        in {"yes_complete", "no_complete", "yes_partial", "no_partial"}
        and "evidence_ref" not in payload
    ):
        payload["evidence_ref"] = "E1:S1"
        return json.dumps(payload)
    return response


class BooleanVerifier:
    def __init__(
        self,
        verdict: str,
        quote: str,
        evidence_ref: str = "E1:S1",
        repair_ref: str | None = None,
    ) -> None:
        refs = [evidence_ref] + ([repair_ref] if repair_ref is not None else [])
        self.responses = [
            json.dumps(
                {
                    "verdict": verdict,
                    "evidence_ref": ref,
                    "evidence_quote": quote,
                },
                ensure_ascii=False,
            )
            for ref in refs
        ]

    def __call__(self, _prompt: str, **_kwargs: Any) -> Any:
        return SimpleNamespace(text=self.responses.pop(0))

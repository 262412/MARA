#!/usr/bin/env python3
"""Produce live QASPER contract-probe rows through the production path.

This artifact is deliberately separate from ``predictions.jsonl``.  A row is
created by the same typed candidate generator, semantic proposition verifier,
independent auditor, verification evidence projection, and terminal result
used by the benchmark route.  The probe does not interpret provider text or
construct verifier/auditor/authority state itself.

The six cases are small, controlled evidence fixtures used to exercise the
provider contract.  Their expected states are an assertion about the live
result, not a source of state.  In particular, the controlled auditor-fault
case succeeds only when the production parser/local auditor rejects the
provider's proposed proof and the terminal path abstains.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from scripts.slurm.qasper_debug_contract_probe_artifact import (  # noqa: F401
    _MODEL_CONTRACT,
    _assert_live_coverage,
    _observed_state,
    _prediction_row,
    _probe_annotation,
    _terminal_snapshot,
    _trace_from_row,
    _write_rows,
)
from scripts.slurm.qasper_debug_contract_probe_cases import (  # noqa: F401
    _AUDITOR_STATUSES,
    _CANDIDATES,
    _JUDGMENTS,
    _PROBE_CASES,
    _QUESTION,
    ProbeCase,
    _build_request_and_bundle,
    _digest,
)
from scripts.slurm.qasper_debug_contract_probe_runtime import (  # noqa: F401
    _attach_call_evidence,
    _default_model_factory,
    _execute_case,
    _model_clients,
    _pipeline,
    _RecordingChatModel,
    _response_finish_reason,
    _response_text,
)


def _run_case(
    case: ProbeCase,
    index: int,
    *,
    base_url: str,
    model: str,
    timeout_seconds: float,
    model_factory: Callable[..., Any],
) -> dict[str, Any]:
    generation_candidate, verifier_candidate, execution, calls = _execute_case(
        case,
        index,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        model_factory=model_factory,
    )
    live_calls = _attach_call_evidence(execution, calls)
    if len(live_calls) < 3:
        raise RuntimeError(
            f"{case.case_id}: expected candidate, proposal, and auditor calls; "
            f"observed {len(live_calls)}"
        )
    return _prediction_row(
        case,
        generation_candidate,
        verifier_candidate,
        execution,
        live_calls,
    )


def run_live_probes(
    base_url: str,
    model: str,
    *,
    timeout_seconds: float = 60.0,
    model_factory: Callable[..., Any] | None = None,
) -> list[dict[str, Any]]:
    factory = model_factory or _default_model_factory
    rows = [
        _run_case(
            case,
            index,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            model_factory=factory,
        )
        for index, case in enumerate(_PROBE_CASES)
    ]
    _assert_live_coverage(rows)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    args = parser.parse_args()
    rows = run_live_probes(
        args.base_url,
        args.model,
        timeout_seconds=args.timeout_seconds,
    )
    _write_rows(args.output, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

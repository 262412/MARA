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
    validate_heterogeneous_provider_config,
)


def _run_case(
    case: ProbeCase,
    index: int,
    *,
    base_url: str,
    model: str,
    auditor_base_url: str,
    auditor_model: str,
    timeout_seconds: float,
    model_factory: Callable[..., Any],
) -> dict[str, Any]:
    generation_candidate, verifier_candidate, execution, calls = _execute_case(
        case,
        index,
        base_url=base_url,
        model=model,
        auditor_base_url=auditor_base_url,
        auditor_model=auditor_model,
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
    auditor_base_url: str | None = None,
    auditor_model: str | None = None,
    timeout_seconds: float = 60.0,
    model_factory: Callable[..., Any] | None = None,
    output_path: Path | None = None,
    audit_path: Path | None = None,
) -> list[dict[str, Any]]:
    factory = model_factory or _default_model_factory
    rows: list[dict[str, Any]] = []
    try:
        validate_heterogeneous_provider_config(
            base_url=base_url,
            model=model,
            auditor_base_url=auditor_base_url,
            auditor_model=auditor_model,
        )
        for index, case in enumerate(_PROBE_CASES):
            rows.append(
                _run_case(
                    case,
                    index,
                    base_url=base_url,
                    model=model,
                    auditor_base_url=str(auditor_base_url or ""),
                    auditor_model=str(auditor_model or ""),
                    timeout_seconds=timeout_seconds,
                    model_factory=factory,
                )
            )
    except Exception as exc:
        if output_path is not None:
            _write_rows(output_path, rows)
            if audit_path is not None:
                _persist_failure_audit(output_path, audit_path, exc)
        raise
    # Publish every real row before evaluating coverage or any other hard
    # gate.  A failed coverage assertion must leave the exact provider rows
    # available to the formal validator and downstream audit tooling.
    if output_path is not None:
        _write_rows(output_path, rows)
        if audit_path is not None:
            _persist_pending_audit(output_path, audit_path)
    _assert_live_coverage(rows)
    return rows


def _persist_failure_audit(
    predictions_path: Path,
    audit_path: Path,
    exc: BaseException,
) -> None:
    from scripts.slurm.validate_qasper_contract_probe import (
        persist_failed_contract_probe_audit,
    )

    persist_failed_contract_probe_audit(
        predictions_path,
        output_path=audit_path,
        failure_evidence={
            "probe_exception": {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
            }
        },
    )


def _persist_pending_audit(predictions_path: Path, audit_path: Path) -> None:
    from scripts.slurm.validate_qasper_contract_probe import (
        persist_failed_contract_probe_audit,
    )

    persist_failed_contract_probe_audit(
        predictions_path,
        output_path=audit_path,
        evaluate_gates=False,
        failure_evidence={
            "probe_execution": {
                "phase": "pre_hard_gate",
                "hard_gate_complete": False,
            }
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--auditor-base-url", required=True)
    parser.add_argument("--auditor-model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--audit-output",
        type=Path,
        help=(
            "Optional formal audit path; defaults to contract_probe_audit.json "
            "beside --output."
        ),
    )
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    args = parser.parse_args()
    output_path = args.output.resolve()
    audit_path = (
        args.audit_output.resolve()
        if args.audit_output is not None
        else output_path.with_name("contract_probe_audit.json")
    )
    try:
        run_live_probes(
            args.base_url,
            args.model,
            auditor_base_url=args.auditor_base_url,
            auditor_model=args.auditor_model,
            timeout_seconds=args.timeout_seconds,
            output_path=output_path,
            audit_path=audit_path,
        )
    except Exception as exc:
        try:
            _persist_failure_audit(output_path, audit_path, exc)
        except Exception as audit_exc:
            raise exc from audit_exc
        raise
    from scripts.slurm.validate_qasper_contract_probe import validate_contract_probe

    validate_contract_probe(output_path, output_path=audit_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

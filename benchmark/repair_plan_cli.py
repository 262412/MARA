from __future__ import annotations

import argparse
import json
from pathlib import Path

from .repair_plan import evaluate_release_gates


def add_repair_gate_command(subparsers: argparse._SubParsersAction) -> None:
    gate_parser = subparsers.add_parser(
        "evaluate-repair-gates",
        help="Evaluate Phase G against the frozen benchmark repair gates",
    )
    gate_parser.add_argument("--phase-b-summary", required=True, type=Path)
    gate_parser.add_argument("--phase-g-summary", required=True, type=Path)
    gate_parser.add_argument("--paired-semantic-ci-low", required=True, type=float)
    gate_parser.add_argument("--token-f1-rescore-delta", required=True, type=float)
    gate_parser.add_argument("--output", required=True, type=Path)


def handle_repair_gate_command(args: argparse.Namespace) -> int | None:
    if args.command != "evaluate-repair-gates":
        return None

    phase_b = json.loads(args.phase_b_summary.read_text(encoding="utf-8"))
    phase_g = json.loads(args.phase_g_summary.read_text(encoding="utf-8"))
    gates = evaluate_release_gates(
        phase_b=phase_b,
        phase_g=phase_g,
        paired_semantic_ci_low=args.paired_semantic_ci_low,
        token_f1_rescore_delta=args.token_f1_rescore_delta,
    )
    release_gate = all(item["passed"] for item in gates.values())
    payload = {"release_gate": release_gate, "gates": gates}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0 if release_gate else 2

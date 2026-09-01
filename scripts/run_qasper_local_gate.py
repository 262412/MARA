"""Run the local QASPER contract gate used before provider-backed probes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Keep this list explicit: it is the reproducible pre-probe contract gate, and
# omissions should be visible in review instead of hidden behind a directory
# glob.  The provider generation and audit paths are both production-path
# tests and must stay in the mandatory local gate.
QASPER_LOCAL_GATE_TESTS: tuple[str, ...] = (
    "libs/ktem/ktem_tests/test_mara_qasper_candidate_evidence_set_binding.py",
    "libs/ktem/ktem_tests/test_mara_semantic_proposition_audit.py",
    "libs/ktem/ktem_tests/test_mara_semantic_proposition_audit_contract.py",
    "libs/ktem/ktem_tests/test_mara_semantic_proposition_contract.py",
    "libs/ktem/ktem_tests/test_mara_semantic_proposition_observability.py",
    "libs/ktem/ktem_tests/test_mara_semantic_proposition_pre_audit.py",
    "libs/ktem/ktem_tests/test_mara_semantic_proposition_recovery_stop.py",
    "libs/ktem/ktem_tests/test_mara_semantic_proposition_schema.py",
    "libs/ktem/ktem_tests/test_mara_semantic_proposition_schema_parser_identity.py",
    "libs/ktem/ktem_tests/test_mara_semantic_audit_repair.py",
    "libs/ktem/ktem_tests/test_mara_semantic_local_consistency.py",
    "libs/ktem/ktem_tests/test_qasper_assertion_scope_contract.py",
    "libs/ktem/ktem_tests/test_qasper_canonical_semantic_pack_alignment.py",
    "libs/ktem/ktem_tests/test_qasper_frozen_audit_authority.py",
    "libs/ktem/ktem_tests/test_qasper_stage2_10396653_selector_characterization.py",
    "benchmark/tests/test_qasper_contract_probe_assertion_scope.py",
    "benchmark/tests/test_qasper_contract_probe_generation.py",
    "benchmark/tests/test_qasper_contract_probe_audit.py",
    "benchmark/tests/test_qasper_contract_probe_natural_payloads.py",
    "benchmark/tests/test_qasper_natural_semantic_pack_probe.py",
    "benchmark/tests/test_qasper_retrieval_index_artifact.py",
    "benchmark/tests/test_qasper_retrieval_index_slurm_contract.py",
    "benchmark/tests/test_qasper_stage12_replay_audit_characterization.py",
    "benchmark/tests/test_qasper_debug_contract_smoke.py",
    "benchmark/tests/test_run_provenance.py",
)


def pytest_command(*pytest_args: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *QASPER_LOCAL_GATE_TESTS,
        *pytest_args,
    ]


def run_gate(*pytest_args: str) -> int:
    command = pytest_command(*pytest_args)
    print("[qasper-local-gate]", " ".join(command), flush=True)
    return subprocess.run(command, cwd=REPO_ROOT, check=False).returncode


def main() -> int:
    return run_gate(*sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())

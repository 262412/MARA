from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEXT_SLURM_SCRIPT = PROJECT_ROOT / "scripts/slurm/text_route_rerun.sbatch"


def test_text_route_slurm_binds_natural_and_formal_runs_to_one_real_index():
    text = TEXT_SLURM_SCRIPT.read_text(encoding="utf-8")

    assert 'RETRIEVAL_INDEX_MODE="${MARA_QASPER_RETRIEVAL_INDEX_MODE:-off}"' in text
    assert "qasper_retrieval_index_artifact_cli" in text
    assert "qasper_natural_semantic_pack_probe" in text
    assert '--retrieval-index-artifact "$RETRIEVAL_INDEX_ARTIFACT"' in text
    assert "--retrieval-index-restore-audit" in text
    assert '"$RETRIEVAL_INDEX_RESTORE_AUDIT"' in text
    assert text.index("mara_bootstrap_benchmark_runtime") < text.index(
        "retrieval_index_restore"
    )
    configure_invocation = (
        '"$MARA_BENCHMARK_PYTHON" "${HPC_HOME}/configure_mara_local_models.py"'
    )
    assert text.index("retrieval_index_restore") < text.index(configure_invocation)
    assert text.index("qasper_retrieval_index_artifact_cli create") < text.index(
        "qasper_natural_semantic_pack_probe"
    )

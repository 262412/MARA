import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCANNED_ROOTS = (
    REPO_ROOT / "benchmark",
    REPO_ROOT / "libs",
    REPO_ROOT / "scripts",
    REPO_ROOT / "docs" / "development",
    REPO_ROOT / "docs" / "superpowers",
)
DEVELOPMENT_PHASE_NAME = re.compile(r"(^|[_-])phase[1-4][a-z]?($|[_.-])", re.I)
SOURCE_SUFFIXES = {".py", ".sbatch", ".sh", ".md"}


def test_code_and_operational_files_use_descriptive_names():
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for root in SCANNED_ROOTS
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix in SOURCE_SUFFIXES
        and DEVELOPMENT_PHASE_NAME.search(path.name)
    ]

    assert offenders == []

"""Create only a task fixture archive, using the same child isolation entrypoint."""

import os
import sys
import zipfile
from pathlib import Path

from pytest_runtime_isolation import start_process_test_runtime


def main():
    if (
        os.environ.get("MARA_DIAGNOSTIC_ISOLATION_REQUIRED") != "1"
        or os.environ.get("MARA_DIAGNOSTIC_CHILD") != "1"
    ):
        raise RuntimeError("Archive fixture requires the isolated browser runner")
    runtime = start_process_test_runtime()
    try:
        target = Path(sys.argv[1]).resolve()
        evidence = Path(os.environ["MARA_DIAGNOSTIC_EVIDENCE_DIR"]).resolve()
        if not target.is_relative_to(evidence):
            raise RuntimeError("Archive fixture output is not owned")
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr(sys.argv[2], sys.argv[3])
    finally:
        runtime.close()


if __name__ == "__main__":
    main()

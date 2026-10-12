"""Run the published case again using the installed reviewer package and real APIs."""

import argparse
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from configuration import configure

CASE = Path(__file__).parent


def save(path, payload):
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )


def execute(output):
    configure(output)
    from capture_provider import CALLS
    from ktem.docqa import DocQARequest
    from slide_cli.docqa_runtime import create_docqa_runtime

    runtime = create_docqa_runtime()
    shutil.copytree(CASE / "inputs", output / "inputs")
    files = sorted((output / "inputs").glob("*.txt"))
    indexed = runtime.index_paths([str(path) for path in files])
    save(output / "index.json", indexed.as_dict())
    if indexed.failures or len(indexed.successes) != 2:
        raise RuntimeError("Both sources must index successfully before asking")
    identities = {record.name: record.file_id for record in runtime.list_files()}
    for label, source in [
        ("before", "harbor-operations.txt"),
        ("after", "harbor-data-policy.txt"),
    ]:
        request = json.loads(
            (CASE / f"records/{label}-request.json").read_text(encoding="utf-8")
        )
        request["selected_file_ids"] = [identities[source]]
        CALLS.clear()
        turn = DocQARequest(**request)
        save(output / f"{label}-request.json", asdict(turn))
        response = runtime.run_turn(turn)
        save(output / f"{label}-response.json", response.as_dict())
        save(output / f"{label}-provider-calls.json", CALLS)
        print(label, response.verify_decision["status"], response.answer, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execute(args.output.resolve())

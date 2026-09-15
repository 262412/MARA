"""Exercise the pinned scanner in an exclusive, disposable Git fixture.

Run outside the checkout with --work-dir NEW_DIRECTORY. Generated credentials
never enter the MARA repository. Directory findings retain the scanner's actual
path spelling; CI additionally exercises its /repo mount against full history.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEST_PATH = "libs/ktem/ktem_tests/test_chat_javascript_resources.py"


def _public_digest() -> str:
    tree = ast.parse((REPO / TEST_PATH).read_text(encoding="utf-8"))
    expected = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "EXPECTED" for t in node.targets)
    )["fetch_api_key_js"]
    script = (REPO / "libs/ktem/ktem/assets/js/fetch_api_key.js").read_text(
        encoding="utf-8"
    )
    assert hashlib.sha256(script.encode("utf-8")).hexdigest() == expected
    return expected


def _fixture(root: Path, files: dict[str, str]) -> None:
    root.mkdir()
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    commands = (
        ["init", "--quiet"],
        ["config", "core.hooksPath", str(root / "empty-hooks")],
        ["add", "--", *files],
        [
            "-c",
            "user.name=G0 fixture",
            "-c",
            "user.email=fixture@invalid",
            "commit",
            "--quiet",
            "-m",
            "Generated scanner controls",
        ],
    )
    for args in commands:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _scan(scanner: Path, root: Path, config: Path, mode: str, target: str) -> dict:
    output = root.parent / f"{root.name}-{mode}"
    command = [
        str(scanner),
        mode,
        target,
        "--config",
        str(config),
        "--redact",
        "--verbose",
        "--no-banner",
        "--no-color",
        "--exit-code",
        "1",
        "--report-format",
        "json",
        "--report-path",
        str(output.with_suffix(".json")),
    ]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    output.with_suffix(".log").write_text(
        result.stdout + result.stderr, encoding="utf-8"
    )
    findings = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
    return {
        "mode": mode,
        "command": command,
        "exit_code": result.returncode,
        "findings": [
            {key: f[key] for key in ("RuleID", "File", "StartLine", "Commit")}
            for f in findings
        ],
    }


def check(scanner: Path, destination: Path, config: Path) -> dict:
    destination = destination.resolve()
    if destination == REPO or REPO in destination.parents:
        raise ValueError("Generated credentials must stay outside the checkout")
    destination.mkdir()
    version = subprocess.check_output([str(scanner), "version"], text=True).strip()
    assert version == "8.24.3", version
    digest = _public_digest()
    # Deterministic, high-entropy controls are generated only in the owned fixture.
    changed = hashlib.sha256(b"G0 changed digest control").hexdigest()
    other = hashlib.sha256(b"G0 unrelated credential control").hexdigest()
    cases: dict[str, tuple[dict[str, str], set[str]]] = {
        "public": ({TEST_PATH: f'"fetch_api_key_js": "{digest}"\n'}, set()),
        "changed": (
            {TEST_PATH: f'"fetch_api_key_js": "{changed}"\n'},
            {"generic-api-key"},
        ),
        "other_path": (
            {"other.py": f'"fetch_api_key_js": "{digest}"\n'},
            {"generic-api-key"},
        ),
        "other_key": (
            {TEST_PATH: f'"service_api_key": "{other}"\n'},
            {"generic-api-key"},
        ),
        "custom": (
            {"promptui/tunnel.py": f'token = "{other}"\n'},
            {"mara-promptui-frp-token"},
        ),
    }
    records = []
    for name, (files, expected) in cases.items():
        root = destination / name
        _fixture(root, files)
        for mode, target in (("git", "."), ("dir", next(iter(files)))):
            record = _scan(scanner, root, config, mode, target)
            rules = {finding["RuleID"] for finding in record["findings"]}
            record.update(case=name, expected_rules=sorted(expected))
            record["passed"] = (
                expected <= rules
                and bool(rules) == bool(expected)
                and record["exit_code"] == int(bool(expected))
            )
            records.append(record)
    report = {
        "version": version,
        "binary_sha256": hashlib.sha256(scanner.read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "public_digest": digest,
        "records": records,
        "passed": all(record["passed"] for record in records),
    }
    (destination / "result.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gitleaks", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=REPO / ".gitleaks.toml")
    args = parser.parse_args()
    report = check(args.gitleaks.resolve(), args.work_dir, args.config.resolve())
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / "scripts" / "codebase_hygiene_baseline.json"
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}
FUNCTION_LINE_BUDGET = 80
CLASS_LINE_BUDGET = 300
MODULE_LINE_BUDGET = 600


@dataclass
class FileMetrics:
    path: str
    module_lines: int
    functions: dict[str, int] = field(default_factory=dict)
    classes: dict[str, int] = field(default_factory=dict)
    non_actionable_broad_exceptions: int = 0

    def has_baseline_entry(self) -> bool:
        return (
            self.module_lines > MODULE_LINE_BUDGET
            or any(length > FUNCTION_LINE_BUDGET for length in self.functions.values())
            or any(length > CLASS_LINE_BUDGET for length in self.classes.values())
            or self.non_actionable_broad_exceptions > 0
        )

    def to_baseline_entry(self) -> dict:
        return {
            "module_lines": self.module_lines,
            "functions": {
                name: length
                for name, length in sorted(self.functions.items())
                if length > FUNCTION_LINE_BUDGET
            },
            "classes": {
                name: length
                for name, length in sorted(self.classes.items())
                if length > CLASS_LINE_BUDGET
            },
            "non_actionable_broad_exceptions": self.non_actionable_broad_exceptions,
        }


@dataclass
class Violation:
    path: str
    message: str


class MetricsVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.functions: dict[str, int] = {}
        self.classes: dict[str, int] = {}
        self.non_actionable_broad_exceptions = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_callable(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_callable(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        name = self._qualified_name(node.name)
        self.classes[name] = self._node_length(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if self._is_broad_exception(node) and not self._is_actionable(node):
            self.non_actionable_broad_exceptions += 1
        self.generic_visit(node)

    def _record_callable(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        name = self._qualified_name(node.name)
        self.functions[name] = self._node_length(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def _qualified_name(self, name: str) -> str:
        return ".".join([*self.stack, name])

    @staticmethod
    def _node_length(node: ast.AST) -> int:
        end_line = getattr(node, "end_lineno", None) or node.lineno
        return end_line - node.lineno + 1

    @staticmethod
    def _is_broad_exception(node: ast.ExceptHandler) -> bool:
        if node.type is None:
            return True
        if isinstance(node.type, ast.Name):
            return node.type.id in {"Exception", "BaseException"}
        if isinstance(node.type, ast.Tuple):
            return any(
                isinstance(item, ast.Name) and item.id in {"Exception", "BaseException"}
                for item in node.type.elts
            )
        return False

    @staticmethod
    def _is_actionable(node: ast.ExceptHandler) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Raise):
                return True
            if isinstance(child, ast.Call) and _is_diagnostic_call(child):
                return True
        return False


def _is_diagnostic_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in {"print"}
    if not isinstance(func, ast.Attribute):
        return False
    attr = func.attr
    if attr in {"debug", "info", "warning", "error", "exception", "critical"}:
        return True
    return attr in {"echo", "Warning", "Error"}


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _is_python_file(path: Path) -> bool:
    return path.suffix == ".py" and not set(path.parts).intersection(EXCLUDED_PARTS)


def _tracked_python_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode == 0:
        paths = []
        for line in result.stdout.splitlines():
            if not line:
                continue
            path = ROOT / line
            if path.exists():
                paths.append(path)
        return paths
    return sorted(path for path in ROOT.rglob("*.py") if _is_python_file(path))


def _selected_python_files(raw_paths: list[str]) -> list[Path]:
    if not raw_paths:
        return [path for path in _tracked_python_files() if _is_python_file(path)]
    paths = [Path(raw_path) for raw_path in raw_paths]
    return [path for path in paths if path.exists() and _is_python_file(path)]


def collect_file_metrics(path: Path) -> FileMetrics:
    text = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(text, filename=_display_path(path))
    visitor = MetricsVisitor()
    visitor.visit(tree)
    return FileMetrics(
        path=_display_path(path),
        module_lines=len(text.splitlines()),
        functions=visitor.functions,
        classes=visitor.classes,
        non_actionable_broad_exceptions=visitor.non_actionable_broad_exceptions,
    )


def load_baseline(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "files": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def write_baseline(path: Path, metrics: list[FileMetrics]) -> None:
    payload = {
        "version": 1,
        "budgets": {
            "function_lines": FUNCTION_LINE_BUDGET,
            "class_lines": CLASS_LINE_BUDGET,
            "module_lines": MODULE_LINE_BUDGET,
        },
        "files": {
            metric.path: metric.to_baseline_entry()
            for metric in sorted(metrics, key=lambda item: item.path)
            if metric.has_baseline_entry()
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def compare_to_baseline(metric: FileMetrics, baseline: dict) -> list[Violation]:
    file_baseline = baseline.get("files", {}).get(metric.path, {})
    violations = []
    violations.extend(_module_violations(metric, file_baseline))
    violations.extend(_function_violations(metric, file_baseline))
    violations.extend(_class_violations(metric, file_baseline))
    violations.extend(_broad_exception_violations(metric, file_baseline))
    return violations


def _module_violations(metric: FileMetrics, baseline: dict) -> list[Violation]:
    allowed = int(baseline.get("module_lines", 0) or 0)
    if metric.module_lines > MODULE_LINE_BUDGET and metric.module_lines > allowed:
        return [
            Violation(
                metric.path,
                f"module too long: {metric.module_lines} lines "
                f"(budget {MODULE_LINE_BUDGET}, baseline {allowed})",
            )
        ]
    return []


def _function_violations(metric: FileMetrics, baseline: dict) -> list[Violation]:
    allowed_functions = baseline.get("functions", {})
    violations = []
    for name, length in sorted(metric.functions.items()):
        allowed = int(allowed_functions.get(name, 0) or 0)
        if length > FUNCTION_LINE_BUDGET and length > allowed:
            violations.append(
                Violation(
                    metric.path,
                    f"function too long: {name} has {length} lines "
                    f"(budget {FUNCTION_LINE_BUDGET}, baseline {allowed})",
                )
            )
    return violations


def _class_violations(metric: FileMetrics, baseline: dict) -> list[Violation]:
    allowed_classes = baseline.get("classes", {})
    violations = []
    for name, length in sorted(metric.classes.items()):
        allowed = int(allowed_classes.get(name, 0) or 0)
        if length > CLASS_LINE_BUDGET and length > allowed:
            violations.append(
                Violation(
                    metric.path,
                    f"class too long: {name} has {length} lines "
                    f"(budget {CLASS_LINE_BUDGET}, baseline {allowed})",
                )
            )
    return violations


def _broad_exception_violations(metric: FileMetrics, baseline: dict) -> list[Violation]:
    allowed = int(baseline.get("non_actionable_broad_exceptions", 0) or 0)
    current = metric.non_actionable_broad_exceptions
    if current > allowed:
        return [
            Violation(
                metric.path,
                "non-actionable broad exception count increased: "
                f"{current} handlers (baseline {allowed})",
            )
        ]
    return []


def _collect_metrics(paths: list[Path]) -> tuple[list[FileMetrics], list[Violation]]:
    metrics = []
    violations = []
    for path in paths:
        try:
            metrics.append(collect_file_metrics(path))
        except SyntaxError as exc:
            violations.append(Violation(_display_path(path), f"parse error: {exc}"))
    return metrics, violations


def _print_violations(violations: list[Violation]) -> None:
    print("Codebase hygiene ratchet violations:")
    for violation in violations:
        print(f"- {violation.path}: {violation.message}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enforce codebase hygiene budgets against the current baseline."
    )
    parser.add_argument("paths", nargs="*", help="Python files to check.")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Path to the hygiene baseline JSON file.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Rewrite the baseline using the selected files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    paths = _selected_python_files(args.paths)
    metrics, violations = _collect_metrics(paths)
    if args.update_baseline:
        write_baseline(args.baseline, metrics)
        print(f"Wrote codebase hygiene baseline: {args.baseline}")
        return 0

    baseline = load_baseline(args.baseline)
    for metric in metrics:
        violations.extend(compare_to_baseline(metric, baseline))
    if violations:
        _print_violations(violations)
        return 1
    print("No codebase hygiene ratchet violations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

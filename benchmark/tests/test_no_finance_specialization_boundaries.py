from __future__ import annotations

import ast
from pathlib import Path

GENERIC_RUNTIME_MODULES = (
    "benchmark/citation_metrics.py",
    "benchmark/diagnostics.py",
    "benchmark/docqa_evidence_projection.py",
    "benchmark/docqa_runtime_sources.py",
    "benchmark/engines.py",
    "benchmark/evidence_adapters.py",
    "benchmark/manifest.py",
    "benchmark/manifest_templates.py",
    "benchmark/metrics.py",
    "benchmark/runner.py",
    "benchmark/page_alignment.py",
    "benchmark/reports.py",
    "benchmark/scoring.py",
    "benchmark/summary.py",
    "libs/ktem/ktem/docqa/evidence_text.py",
    "libs/ktem/ktem/docqa/verification.py",
    "libs/ktem/ktem/reasoning/mara_controller.py",
    "libs/ktem/ktem/reasoning/mara_route_retrieval.py",
)


def test_generic_runtime_layers_do_not_import_finance_specific_modules():
    repo = Path(__file__).resolve().parents[2]

    offenders = [
        relative_path
        for relative_path in GENERIC_RUNTIME_MODULES
        if _imports_finance_specific_module(repo / relative_path)
    ]

    assert offenders == []


def test_generic_runtime_layers_do_not_branch_on_financebench_identifiers():
    repo = Path(__file__).resolve().parents[2]

    offenders = [
        relative_path
        for relative_path in GENERIC_RUNTIME_MODULES
        if _contains_finance_specific_identifier(repo / relative_path)
    ]

    assert offenders == []


def _imports_finance_specific_module(path: Path) -> bool:
    if not path.exists():
        return False
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(_module_is_finance_specific(alias.name) for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _module_is_finance_specific(module):
                return True
    return False


def _module_is_finance_specific(module: str) -> bool:
    return any(
        part.startswith("finance") for part in str(module or "").strip(".").split(".")
    )


def _contains_finance_specific_identifier(path: Path) -> bool:
    if not path.exists():
        return False
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and _text_is_finance_specific(node.id):
            return True
        if isinstance(node, ast.Attribute) and _text_is_finance_specific(node.attr):
            return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _text_is_finance_specific(node.value):
                return True
    return False


def _text_is_finance_specific(value: str) -> bool:
    normalized = value.lower()
    return "financebench" in normalized or "finance_verification" in normalized

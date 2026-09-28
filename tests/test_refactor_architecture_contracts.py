"""Direction guards for accepted extractions, not a whole-repository graph.

Behavior, patch and cold-import tests stay with their existing owners. These
guards inspect imports (including relative/literal dynamic imports), not source
spelling or line counts. Computed classpaths still need consumer tests.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ("gradio", "click", "ktem.pages", "ktem.main")
RUNTIME = ("ktem.docqa.runtime", "ktem.docqa._runtime")
# module: (package root, forbidden dependencies, require stdlib at import time)
BOUNDARIES = {
    "ktem_contracts.file_selection": (
        "libs/ktem",
        ("ktem", "kotaemon", "slide_cli", *UI),
        True,
    ),
    "ktem.docqa.finance_plan_policy": (
        "libs/ktem",
        (*UI, *RUNTIME, "ktem.docqa.query_planning"),
        False,
    ),
    "ktem.docqa.evidence_binding_policy": (
        "libs/ktem",
        (*UI, *RUNTIME, "ktem.docqa.query_evidence_binding"),
        False,
    ),
    "ktem.pages.chat.file_browser_rendering": (
        "libs/ktem",
        ("ktem", "kotaemon", "slide_cli", "gradio", "sqlmodel", "sqlalchemy"),
        True,
    ),
    "slide_cli.docqa_inspection": (
        "libs/slide_cli",
        (*UI, *RUNTIME, "slide_cli.docqa_runtime"),
        True,
    ),
    "kotaemon.agents.tools.mcp_operation": (
        "libs/kotaemon",
        (
            *UI,
            "ktem",
            "mcp",
            "kotaemon.agents.tools.mcp",
            "kotaemon.agents.tools.mcp_session",
        ),
        True,
    ),
    "kotaemon.agents.tools.mcp_session": (
        "libs/kotaemon",
        (*UI, "ktem", "kotaemon.agents.tools.mcp"),
        True,
    ),
    "kotaemon.agents.tools.mcp": ("libs/kotaemon", ("mcp", "ktem"), False),
    "slide_cli.deck_export": (
        "libs/slide_cli",
        (*UI, *RUNTIME, "slide_cli.deck", "slide_cli.runtime"),
        True,
    ),
}


class _Imports(ast.NodeVisitor):
    def __init__(self, module):
        self.package = module.rpartition(".")[0]
        self.lazy = False
        self.aliases = {"__import__": "__import__"}
        self.records = []
        self.postponed_annotations = False

    def visit_Module(self, node):
        self.postponed_annotations = any(
            isinstance(item, ast.ImportFrom)
            and item.module == "__future__"
            and any(alias.name == "annotations" for alias in item.names)
            for item in node.body
        )
        self.generic_visit(node)

    def add(self, name, node):
        if name.startswith("."):
            name = importlib.util.resolve_name(name, self.package)
        self.records.append((name, self.lazy, node.lineno))

    def visit_Import(self, node):
        for alias in node.names:
            self.add(alias.name, node)
            local = alias.asname or alias.name.split(".")[0]
            self.aliases[local] = alias.name if alias.asname else local

    def visit_ImportFrom(self, node):
        base = "." * node.level + (node.module or "")
        if node.level:
            base = importlib.util.resolve_name(base, self.package)
        self.add(base, node)
        for alias in node.names:
            target = base + "." + alias.name
            self.add(target, node)
            self.aliases[alias.asname or alias.name] = target

    def visit_Call(self, node):
        name = ast.unparse(node.func)
        first, dot, rest = name.partition(".")
        resolved = self.aliases.get(first, first) + (dot + rest if dot else "")
        if resolved in ("importlib.import_module", "__import__") and node.args:
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                self.add(argument.value, node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Defaults/decorators execute when a function is defined, not called.
        for expression in [
            *node.decorator_list,
            *node.args.defaults,
            *node.args.kw_defaults,
        ]:
            if expression is not None:
                self.visit(expression)
        if not self.postponed_annotations:
            for argument in [
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
                node.args.vararg,
                node.args.kwarg,
            ]:
                if argument is not None and argument.annotation is not None:
                    self.visit(argument.annotation)
            if node.returns is not None:
                self.visit(node.returns)
        was_lazy = self.lazy
        self.lazy = True
        for statement in node.body:
            self.visit(statement)
        self.lazy = was_lazy

    visit_AsyncFunctionDef = visit_FunctionDef


def _violations(source, module):
    _, forbidden, cold = BOUNDARIES[module]
    visitor = _Imports(module)
    visitor.visit(ast.parse(source))
    failures = []
    for name, lazy, line in visitor.records:
        reverse = any(
            name == prefix or name.startswith(prefix + ".") for prefix in forbidden
        )
        if "ktem.docqa._runtime" in forbidden:
            reverse |= name.startswith("ktem.docqa._runtime_")
        if reverse:
            failures.append((line, name, "reverse dependency"))
        if cold and not lazy and name.split(".")[0] not in sys.stdlib_module_names:
            failures.append((line, name, "eager dependency"))
    return failures


@pytest.mark.parametrize("module", BOUNDARIES)
def test_extracted_owner_dependencies(module):
    package, _, _ = BOUNDARIES[module]
    path = ROOT / package / (module.replace(".", "/") + ".py")
    assert _violations(path.read_text(encoding="utf-8"), module) == []


@pytest.mark.parametrize("module", BOUNDARIES)
@pytest.mark.parametrize("syntax", ["absolute", "relative", "dynamic", "lazy"])
def test_every_guard_rejects_a_reverse_dependency(module, syntax):
    forbidden = BOUNDARIES[module][1][-1]
    package = module.rpartition(".")[0]
    if syntax == "absolute":
        source = f"import {forbidden} as facade"
    elif syntax == "relative":
        # Also exercise `from . import facade`, not only `from .facade import x`.
        common = 0
        for left, right in zip(package.split("."), forbidden.split(".")):
            if left != right:
                break
            common += 1
        if common:
            dots = "." * (len(package.split(".")) - common + 1)
            remainder = forbidden.split(".")[common:]
            source = f"from {dots}{'.'.join(remainder[:-1])} import {remainder[-1]}"
        else:
            source = f"from {forbidden} import facade"
    elif syntax == "dynamic":
        source = f"from importlib import import_module as load\nload('{forbidden}')"
    else:
        source = f"def late():\n    import {forbidden}"
    failures = _violations(source, module)
    assert any(kind == "reverse dependency" for _, _, kind in failures)


@pytest.mark.parametrize("module", [m for m, rule in BOUNDARIES.items() if rule[2]])
@pytest.mark.parametrize(
    "syntax", ["import", "class", "default", "decorator", "annotation"]
)
def test_cold_guards_reject_eager_heavy_loads(module, syntax):
    sources = {
        "import": "import sqlalchemy as database",
        "class": "class Query:\n    import sqlalchemy",
        "default": "def query(database=__import__('sqlalchemy')): pass",
        "decorator": "@__import__('sqlalchemy').decorator\ndef query(): pass",
        "annotation": "def query() -> __import__('sqlalchemy').Row: pass",
    }
    assert any(
        kind == "eager dependency"
        for _, _, kind in _violations(sources[syntax], module)
    )


@pytest.mark.parametrize(
    "module,source",
    [
        (
            "slide_cli.docqa_inspection",
            "def query():\n    from ktem.db.models import engine",
        ),
        (
            "kotaemon.agents.tools.mcp_session",
            "async def connect():\n    from mcp import ClientSession",
        ),
        ("kotaemon.agents.tools.mcp", "from .mcp_session import initialized_session"),
        (
            "ktem.docqa.finance_plan_policy",
            "from .finance_query_planning import financial_periods",
        ),
        (
            "ktem.docqa.evidence_binding_policy",
            "from .query_evidence_binding_support import item_for_raw_id",
        ),
        (
            "ktem.pages.chat.file_browser_rendering",
            "import os\ndef suffix(name): return os.path.splitext(name)[1]",
        ),
        (
            "slide_cli.deck_export",
            "import subprocess\ndef convert(args): return subprocess.run(args)",
        ),
        (
            "kotaemon.agents.tools.mcp_operation",
            "import asyncio\nasync def run(operation): return await operation()",
        ),
        (
            "ktem_contracts.file_selection",
            "from typing import Any\ndef normalize(value: Any): return value",
        ),
    ],
)
def test_guards_allow_actual_helper_and_lazy_integration_shapes(module, source):
    assert _violations(source, module) == []


def test_relative_dynamic_reverse_dependency_and_docstring_false_positive():
    module = "slide_cli.deck_export"
    assert _violations(
        "import importlib as imports\nimports.import_module('.deck', __package__)",
        module,
    )
    assert (
        _violations('"import slide_cli.deck"\n# import slide_cli.runtime\n', module)
        == []
    )


def _rendering_io(source):
    tree = ast.parse(source)
    imports = _Imports("ktem.pages.chat.file_browser_rendering")
    imports.visit(tree)
    io_calls = {
        "open",
        "builtins.open",
        "io.open",
        "os.open",
        "os.stat",
        "os.listdir",
        "os.scandir",
        "os.remove",
        "os.unlink",
        "os.path.exists",
        "os.path.isfile",
        "os.path.isdir",
    }
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            first, dot, rest = name.partition(".")
            resolved = imports.aliases.get(first, first) + (dot + rest if dot else "")
            path_read = False
            if isinstance(node.func, ast.Attribute) and isinstance(
                node.func.value, ast.Call
            ):
                constructor = ast.unparse(node.func.value.func)
                first, dot, rest = constructor.partition(".")
                constructor = imports.aliases.get(first, first) + (
                    dot + rest if dot else ""
                )
                path_read = constructor in {
                    "pathlib.Path",
                    "pathlib.PosixPath",
                    "pathlib.WindowsPath",
                } and node.func.attr in {
                    "open",
                    "read_text",
                    "read_bytes",
                    "write_text",
                    "write_bytes",
                    "exists",
                    "is_file",
                    "is_dir",
                    "stat",
                    "iterdir",
                    "glob",
                    "rglob",
                    "unlink",
                    "mkdir",
                    "rename",
                    "replace",
                }
            if resolved in io_calls or path_read:
                found.append(resolved)
    return found


def test_file_rendering_does_not_acquire_filesystem_io():
    path = ROOT / "libs/ktem/ktem/pages/chat/file_browser_rendering.py"
    assert _rendering_io(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "source",
    [
        "open('file')",
        "from builtins import open as read\nread('file')",
        "import os as system\nsystem.listdir('.')",
        "from os.path import exists as present\npresent('file')",
        "from pathlib import Path as P\nP('file').read_text()",
    ],
)
def test_rendering_guard_rejects_io_but_allows_path_label_operations(source):
    assert _rendering_io(source)
    assert _rendering_io("import os\nos.path.splitext('file.pdf')") == []
    assert _rendering_io("from pathlib import Path\nPath('file.pdf').suffix") == []

import ast
import builtins
import importlib
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "kotaemon"
ALLOWED_KTEM_IMPORT_FILES = {
    "__init__.py",
    "cli.py",
    "indices/qa/citation_qa.py",
    "indices/rankings/cohere.py",
}


def _clear_modules(*module_names: str):
    for module_name in module_names:
        sys.modules.pop(module_name, None)


def _import_with_blocked_ktem(monkeypatch, module_name: str):
    attempted = []
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ktem" or name.startswith("ktem."):
            attempted.append(name)
            raise ModuleNotFoundError(name)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    module = importlib.import_module(module_name)
    return module, attempted


class _KtemImportCollector(ast.NodeVisitor):
    def __init__(self):
        self.records = []
        self._function_depth = 0

    def visit_FunctionDef(self, node):
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def visit_AsyncFunctionDef(self, node):
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == "ktem" or alias.name.startswith("ktem."):
                self.records.append(
                    {
                        "lineno": node.lineno,
                        "name": alias.name,
                        "inside_function": self._function_depth > 0,
                    }
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module and (node.module == "ktem" or node.module.startswith("ktem.")):
            self.records.append(
                {
                    "lineno": node.lineno,
                    "name": node.module,
                    "inside_function": self._function_depth > 0,
                }
            )
        self.generic_visit(node)


def test_kotaemon_import_defers_runtime_bootstrap_until_called(monkeypatch):
    _clear_modules("kotaemon", "ktem", "ktem.runtime_bootstrap")

    module, attempted = _import_with_blocked_ktem(monkeypatch, "kotaemon")

    assert module is not None
    assert attempted == []
    assert module.bootstrap_runtime_settings() is None
    assert attempted == ["ktem.runtime_bootstrap"]


def test_citation_qa_import_does_not_require_ktem(monkeypatch):
    _clear_modules(
        "kotaemon.indices.qa.citation_qa",
        "kotaemon.indices.qa.citation_qa_inline",
        "ktem",
        "ktem.llms.manager",
        "ktem.reasoning.prompt_optimization.mindmap",
        "ktem.utils.render",
    )

    module, attempted = _import_with_blocked_ktem(
        monkeypatch, "kotaemon.indices.qa.citation_qa"
    )

    assert module.AnswerWithContextPipeline
    assert attempted == []


def test_core_package_ktem_imports_are_runtime_local_and_allowlisted():
    discovered_files = set()
    module_level_imports = []

    for path in PACKAGE_ROOT.rglob("*.py"):
        relative_path = path.relative_to(PACKAGE_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        collector = _KtemImportCollector()
        collector.visit(tree)

        if not collector.records:
            continue

        discovered_files.add(relative_path)
        module_level_imports.extend(
            f"{relative_path}:{record['lineno']}:{record['name']}"
            for record in collector.records
            if not record["inside_function"]
        )

    assert discovered_files <= ALLOWED_KTEM_IMPORT_FILES
    assert module_level_imports == []

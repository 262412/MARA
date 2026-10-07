"""Check the installed budget facade and stage mechanism outside the checkout."""

import subprocess
from pathlib import Path


def run_route_smoke(python: Path, cwd: Path, env: dict[str, str]) -> None:
    validation = """
import os, signal, sys, threading
from pathlib import Path
from types import SimpleNamespace
assert 'PYTHONPATH' not in os.environ
def offline(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'sqlite3.connect'):
        raise RuntimeError('Installed route mechanism attempted external IO')
sys.addaudithook(offline)
from ktem.docqa import route_stage_runner, route_budget
for module in (route_stage_runner, route_budget):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert route_budget.RouteDeadlineExhausted.__module__ == 'ktem.docqa.route_budget'
request = SimpleNamespace()
marker = object()
assert route_budget.run_blocking_route_stage(request, 'installed', lambda: marker) is marker
assert not hasattr(request, 'route_budget_trace')
assert route_budget._run_with_worker_timeout(2, lambda: marker,
    on_timeout=lambda: route_budget.RouteDeadlineExhausted('installed', None, 2, None),
    on_cancel=lambda: [], event={}) is marker
platforms = ['worker']
if sys.platform.startswith('linux'):
    before = signal.getsignal(signal.SIGALRM)
    assert route_budget._run_with_interruptible_timeout(1, lambda: marker,
        on_timeout=lambda: route_budget.RouteDeadlineExhausted('installed', None, 1, None),
        on_cancel=lambda: [], event={}) is marker
    assert signal.getsignal(signal.SIGALRM) is before
    assert signal.getitimer(signal.ITIMER_REAL) == (0, 0)
    platforms.append('signal')
print('[wheel-smoke] installed route facade and mechanisms passed:', sys.platform, platforms)
"""
    clean_env = env.copy()
    clean_env.pop("PYTHONPATH", None)
    subprocess.run(
        [str(python), "-B", "-c", validation], cwd=cwd, env=clean_env, check=True
    )


def run_preparation_smoke(python: Path, cwd: Path, env: dict[str, str]) -> None:
    validation = """
from pathlib import Path
from types import SimpleNamespace
import sys

import ktem.docqa.runtime as runtime_module
from ktem.docqa import pipeline_preparation
from ktem.docqa._runtime_models import DocQARequest, _PreparedPipeline

prefix = Path(sys.prefix).resolve()
for module in (runtime_module, pipeline_preparation):
    assert Path(module.__file__).resolve().is_relative_to(prefix), module.__file__
calls = []
pipeline = SimpleNamespace()

class Reasoning:
    @staticmethod
    def get_info():
        return {'id': 'wheel'}

    @staticmethod
    def get_pipeline(settings, state, retrievers):
        calls.append((settings, state, retrievers))
        return pipeline

runtime_module.reasonings = {'wheel': Reasoning}
runtime = object.__new__(runtime_module.DocQARuntime)
runtime._resolve_user_id = lambda user: 'wheel-owner'
runtime.load_settings = lambda user: {'reasoning.use': 'wheel'}
runtime._app = SimpleNamespace(index_manager=SimpleNamespace(indices=[]))
runtime.file_index = None
runtime._preview = None
request = DocQARequest(prompt='Installed preparation', qa_scope='document')
prepared = runtime._prepare_pipeline(request)
assert type(prepared) is _PreparedPipeline
assert prepared.pipeline is pipeline and pipeline.docqa_request is request
assert prepared.reasoning_state is calls[0][1]
assert prepared.settings is calls[0][0]
assert prepared.selected_file_ids == [] and prepared.page_number is None
assert calls[0][2] == [] and prepared.reasoning_id == 'wheel'
created, state = runtime.create_pipeline(request)
assert created is pipeline and state is calls[1][1] and len(calls) == 2
print('[wheel-smoke] installed pipeline preparation and legacy create_pipeline passed')
"""
    subprocess.run([str(python), "-c", validation], env=env, cwd=cwd, check=True)

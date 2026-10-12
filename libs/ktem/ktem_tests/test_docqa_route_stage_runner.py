"""The mechanism can run without request state, and import has no execution effects."""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from ktem.docqa import route_budget, route_stage_runner
from ktem_tests.route_stage_test_support import FakeSignal, ScheduledWorker


def test_independent_worker_needs_only_operations():
    worker = ScheduledWorker("start")
    assert (
        route_stage_runner.run_worker_timeout(
            1,
            worker.call,
            on_timeout=lambda: TimeoutError("owned"),
            on_cancel=lambda: None,
            on_stopped=lambda _stopped: None,
            make_event=worker.event,
            make_lock=worker.module().Lock,
            make_thread=worker.thread,
            logger=logging.getLogger(__name__),
        )
        == "value"
    )
    assert worker.calls == ["construct", "start", "backend", "completed"]


def test_independent_signal_uses_narrow_platform_operations():
    signals = FakeSignal()
    marker = object()
    assert (
        route_stage_runner.run_signal_timeout(
            3,
            lambda: marker,
            on_timeout=lambda: TimeoutError("owned"),
            monotonic=lambda: 100,
            get_handler=lambda: signals.getsignal(14),
            get_timer=lambda: signals.getitimer(0),
            set_handler=lambda handler: signals.signal(14, handler),
            set_timer=lambda delay, interval=0: signals.setitimer(0, delay, interval),
        )
        is marker
    )
    assert signals.handler is signals.initial_handler and signals.timer == (0, 0)


def test_clock_patch_after_entry_is_still_observed(monkeypatch):
    signals = FakeSignal(40, 2)
    monkeypatch.setattr(route_budget, "signal", signals)
    monkeypatch.setattr(route_budget, "monotonic", lambda: 100)
    monkeypatch.setattr(route_budget, "_signal_timeout_available", lambda: True)

    def call():
        monkeypatch.setattr(route_budget, "monotonic", lambda: 107)
        return "value"

    assert (
        route_budget._run_with_interruptible_timeout(
            3,
            call,
            on_timeout=lambda: route_budget.RouteDeadlineExhausted("test", 150, 3, 0),
            on_cancel=lambda: [],
            event={},
        )
        == "value"
    )
    assert signals.timer == (33, 2)


def test_runner_cold_import_from_real_parent_has_no_execution_or_io():
    code = r"""
import json, os, signal, sys, threading
import ktem
before = set(sys.modules)
events = []
auditing = True
def audit(event, args):
    if not auditing:
        return
    if event in {'socket.connect', 'socket.getaddrinfo', 'sqlite3.connect'}:
        raise AssertionError(event)
    if event == 'open':
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        ):
            raise AssertionError('write during import')
def observe(name, call):
    def wrapper(*args, **kwargs):
        if auditing:
            events.append(name)
            raise AssertionError(name)
        return call(*args, **kwargs)
    return wrapper
threading.Thread.start = observe('thread.start', threading.Thread.start)
signal.signal = observe('signal.signal', signal.signal)
if hasattr(signal, 'setitimer'):
    signal.setitimer = observe('signal.setitimer', signal.setitimer)
sys.addaudithook(audit)
from ktem.docqa import route_stage_runner
auditing = False
loaded = sorted(set(sys.modules) - before)
blocked = ('ktem.docqa.route_budget', 'ktem.docqa.runtime', 'ktem.docqa.execution',
           'ktem.db', 'ktem.llms', 'sqlmodel', 'sqlalchemy', 'gradio')
assert not any(n == p or n.startswith(p + '.') for n in loaded for p in blocked), loaded
assert events == []
print(json.dumps({'parent': ktem.__file__, 'runner': route_stage_runner.__file__,
                  'new_modules': loaded, 'execution_effects': events}))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
        text=True,
        capture_output=True,
        timeout=20,
        check=True,
    )
    observed = json.loads(result.stdout)
    assert (
        Path(observed["parent"]).resolve()
        == Path(__file__).parents[1] / "ktem/__init__.py"
    )
    assert (
        Path(observed["runner"]).resolve()
        == Path(route_stage_runner.__file__).resolve()
    )
    print(json.dumps(observed))

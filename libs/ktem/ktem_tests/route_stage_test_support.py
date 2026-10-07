"""Controlled scheduler for exact worker/signal call-order characterization."""

import threading
from types import SimpleNamespace
from typing import Any, Callable


class ScheduledWorker:
    def __init__(self, phase, error=None):
        self.phase = phase
        self.error = error
        self.calls = []
        self.waits = []
        self.ready = False
        self.target: Callable[[], None] | None = None
        self.after_wait = lambda: None

    def event(self):
        return SimpleNamespace(set=self.complete, wait=self.wait)

    def complete(self):
        self.calls.append("completed")
        self.ready = True

    def wait(self, seconds):
        self.waits.append(seconds)
        if len(self.waits) == 1 and self.phase in {"wait", "boundary"}:
            assert self.target is not None
            self.target()
        if len(self.waits) == 2:
            self.after_wait()
        return self.ready and not (self.phase == "boundary" and len(self.waits) == 1)

    def thread(self, **kwargs):
        assert set(kwargs) == {"target", "name", "daemon"}
        assert kwargs["name"] == "mara-route-stage" and kwargs["daemon"] is True
        self.calls.append("construct")
        self.target = kwargs["target"]
        return SimpleNamespace(start=self.start)

    def start(self):
        self.calls.append("start")
        if self.phase == "start":
            assert self.target is not None
            self.target()

    def call(self):
        self.calls.append("backend")
        if self.error is not None:
            raise self.error
        return "value"

    def cancel(self):
        self.calls.append("cancel")
        if self.phase == "cancel":
            assert self.target is not None
            self.target()
        return ["LookupError"]

    def module(self):
        return SimpleNamespace(
            Event=self.event, Lock=threading.Lock, Thread=self.thread
        )


class FakeSignal:
    SIGALRM = 14
    ITIMER_REAL = 0

    def __init__(self, delay=0, interval=0):
        self.initial_handler = object()
        self.handler: Any = self.initial_handler
        self.timer = (delay, interval)
        self.calls = []

    def getsignal(self, signum):
        assert signum == self.SIGALRM
        self.calls.append("get_handler")
        return self.handler

    def getitimer(self, kind):
        assert kind == self.ITIMER_REAL
        self.calls.append("get_timer")
        return self.timer

    def signal(self, signum, handler):
        assert signum == self.SIGALRM
        self.calls.append(
            "restore_handler" if handler is self.initial_handler else "install"
        )
        self.handler = handler

    def setitimer(self, kind, delay, interval=0):
        assert kind == self.ITIMER_REAL
        self.calls.append(("timer", delay, interval))
        self.timer = (delay, interval)

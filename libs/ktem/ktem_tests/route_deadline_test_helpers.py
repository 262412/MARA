"""Deterministic scheduling for the route timeout's unresponsive-worker path."""

import threading
from types import SimpleNamespace

from ktem.docqa import route_budget


class RouteClock:
    def __init__(self):
        self.now = 100.0
        self.waits = []
        self.workers_started = 0

    def __call__(self):
        return self.now


class PendingEvent:
    def __init__(self, clock):
        self.clock = clock
        self.ready = False

    def set(self):
        self.ready = True

    def wait(self, timeout):
        if self.ready:
            return True
        self.clock.waits.append(timeout)
        self.clock.now += timeout
        return False


class PendingWorker:
    def __init__(self, clock, **_kwargs):
        self.clock = clock

    def start(self):
        # Model a producer blocked beyond both the call and cancellation waits.
        self.clock.workers_started += 1


def install_pending_route_worker(monkeypatch):
    clock = RouteClock()
    monkeypatch.setattr(route_budget, "monotonic", clock)
    monkeypatch.setattr(route_budget, "_signal_timeout_available", lambda: False)
    monkeypatch.setattr(
        route_budget,
        "threading",
        SimpleNamespace(
            Event=lambda: PendingEvent(clock),
            Lock=threading.Lock,
            Thread=lambda **kwargs: PendingWorker(clock, **kwargs),
        ),
    )
    return clock

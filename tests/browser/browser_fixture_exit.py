"""Shutdown evidence for the owned browser App, before any store is closed."""

import json
import logging
import os
import sys
import time


def release_model(model, output):
    waiting = model.held_started.is_set() and not model.held_finished.is_set()
    model.held_release.set()
    stopped = not waiting or model.held_finished.wait(5)
    (output / "model-gate-teardown.json").write_text(
        json.dumps(
            {
                "waiting": waiting,
                "finished": model.held_finished.is_set(),
                "wait_exited": model.held_finished.is_set(),
                "generator_finished": model.generator_finished.is_set(),
            }
        ),
        encoding="utf-8",
    )
    if not stopped:
        raise RuntimeError("Owned model wait did not exit during fixture teardown")


def producer_state(blocks, model, observer):
    queue = blocks._queue
    return {
        "requests": {
            key: dict(value) for key, value in queue.event_analytics.copy().items()
        },
        "active_jobs": [event._id for job in queue.active_jobs if job for event in job],
        "queued": [
            event._id
            for group in queue.event_queue_per_concurrency_id.values()
            for event in group.queue
        ],
        "generators": model.stream_snapshot(),
        "model_workers": model.worker_snapshot(),
        "writers": [
            {
                "done": writer.done(),
                "alive": writer.thread.is_alive(),
                "cancelled": writer.cancelled(),
            }
            for writer in observer.writers
        ],
    }


def quiescent(state):
    return requests_idle(state) and all(
        item["finished"] is not None for item in state["generators"].values()
    )


def requests_idle(state):
    return (
        not state["active_jobs"]
        and not state["queued"]
        and all(
            item["status"] in {"success", "failed", "cancelled"}
            for item in state["requests"].values()
        )
        and all(not item["project_frames"] for item in state["model_workers"].values())
        and all(not item["alive"] and item["done"] for item in state["writers"])
    )


def finish_app(blocks, model, barriers, observer, output, primary, *, timeout=30):
    """Release independently, then prove producers idle before unwinding stores."""
    failures = []
    releases = []
    for name, release in (
        ("ui", barriers.release_all),
        ("model", lambda: release_model(model, output)),
        ("embedding", observer.release),
        ("deletion_embedding", observer.release_deletion),
    ):
        try:
            release()
            releases.append({"boundary": name, "released": True})
        except Exception as error:
            logging.exception("Owned fixture release failed: %s", name)
            failures.append(error)
            releases.append({"boundary": name, "released": False, "error": repr(error)})
    before = state = None
    idle = False
    try:
        before, state = _drain_producers(blocks, model, observer, timeout)
        idle = quiescent(state)
    except Exception as error:
        logging.exception("Cannot prove owned producers stopped; retaining runtime")
        failures.append(error)
    receipt = {
        "pid": os.getpid(),
        "primary": repr(primary) if primary else None,
        "releases": releases,
        "barriers": barriers.status(),
        "before": before,
        "after": state,
        "quiescent": idle,
        "secondary": [repr(error) for error in failures],
    }
    (output / "producer-teardown.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    if not idle:
        # Do not unwind submission_app's store owners around a live worker.
        # The parent records this exit; the task-owned root remains for diagnosis.
        (output / "cleanup.json").write_text(
            json.dumps(
                {
                    "removed": False,
                    "reason": "producers still active; retained before process termination",
                }
            ),
            encoding="utf-8",
        )
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(2)
    if failures and primary is None:
        raise failures[0]


def _drain_producers(blocks, model, observer, timeout):
    deadline = time.monotonic() + timeout
    state = producer_state(blocks, model, observer)
    before = state
    while not quiescent(state) and time.monotonic() < deadline:
        if requests_idle(state):
            model.close_idle_streams()
        time.sleep(0.05)
        state = producer_state(blocks, model, observer)
    return before, state

"""Controlled delays around real callbacks; never substitute their results."""

import asyncio
import threading
from types import SimpleNamespace

from web_operation_observer import current_operation


class FileBrowserBarriers:
    def __init__(self):
        self.lock = threading.Lock()
        self.gates = {}

    def arm(self, spec):
        key = spec["key"]
        with self.lock:
            if key in self.gates:
                raise ValueError("Use a fresh barrier key")
            self.gates[key] = {
                "spec": dict(spec),
                "entered": False,
                "completed": False,
                "release": threading.Event(),
            }
        return {"armed": key}

    def release(self, key):
        with self.lock:
            self.gates[key]["release"].set()
            deliver = self.gates[key].pop("deliver", None)
        if deliver is not None:
            deliver()
        return {"released": key}

    def release_all(self):
        for key in list(self.gates):
            self.release(key)

    def status(self):
        with self.lock:
            return {
                key: {
                    "spec": gate["spec"],
                    "entered": gate["entered"],
                    "completed": gate["completed"],
                    "session_hash": gate.get("session_hash"),
                    "returned_ids": gate.get("returned_ids"),
                    "operation": gate.get("operation"),
                }
                for key, gate in self.gates.items()
            }

    def observe(self, name, event, values, result):
        matched = self._claim(name, event, values, result)
        if matched is not None:
            if not matched["release"].wait(timeout=40):
                raise RuntimeError("Owned file-browser barrier was not released")
            with self.lock:
                matched["completed"] = True

    def _claim(self, name, event, values, result):
        request = values.get("request")
        operation = current_operation.get()
        with self.lock:
            matched = None
            for gate in self.gates.values():
                spec = gate["spec"]
                if gate["entered"] or name != spec["callback"]:
                    continue
                if "function_id" in spec and operation.get("fn") != spec["function_id"]:
                    continue
                if event != spec.get("event", "return"):
                    continue
                if getattr(request, "username", None) != spec["username"]:
                    continue
                if "session_hash" in spec and spec["session_hash"] != getattr(
                    request, "session_hash", None
                ):
                    continue
                if (
                    "filter_text" in spec
                    and values.get("filter_text") != spec["filter_text"]
                ):
                    continue
                if "file_id" in spec and values.get("file_id") != spec["file_id"]:
                    continue
                if (
                    "filter_version" in spec
                    and operation.get("inputs", {})
                    .get("stamp", {})
                    .get("filterVersion")
                    != spec["filter_version"]
                ):
                    continue
                gate["entered"] = True
                gate["operation"] = operation
                gate["session_hash"] = getattr(request, "session_hash", None)
                if name == "ChatPage.refresh_chat_file_list" and result:
                    gate["returned_ids"] = [row["id"] for row in result[0]]
                matched = gate
                break
        return matched

    def bind_delivery(self, queue):
        """Hold an actual completion message, allowing the worker to finish."""
        original = queue.send_message

        def send_message(event, message):
            if message.msg != "process_completed":
                return original(event, message)
            values = {
                "request": SimpleNamespace(
                    username=event.username, session_hash=event.session_hash
                ),
                "filter_text": event.data.data[5] if len(event.data.data) > 5 else None,
                "file_id": event.data.data[0] if event.data.data else None,
            }
            gate = self._claim(event.fn.name, "delivery", values, None)
            if gate is None:
                return original(event, message)
            loop = asyncio.get_running_loop()

            def deliver():
                original(event, message)
                with self.lock:
                    gate["completed"] = True

            with self.lock:
                gate["deliver"] = lambda: loop.call_soon_threadsafe(deliver)
                released = gate["release"].is_set()
            if released:
                self.release(gate["spec"]["key"])

        queue.send_message = send_message

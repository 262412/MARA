"""Controlled delays around real callbacks; never substitute their results."""

import threading


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
        return {"released": key}

    def release_all(self):
        with self.lock:
            for gate in self.gates.values():
                gate["release"].set()

    def status(self):
        with self.lock:
            return {
                key: {
                    "spec": gate["spec"],
                    "entered": gate["entered"],
                    "completed": gate["completed"],
                    "session_hash": gate.get("session_hash"),
                    "returned_ids": gate.get("returned_ids"),
                }
                for key, gate in self.gates.items()
            }

    def observe(self, name, event, values, result):
        request = values.get("request")
        with self.lock:
            matched = None
            for gate in self.gates.values():
                spec = gate["spec"]
                if gate["entered"] or name != spec["callback"]:
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
                gate["entered"] = True
                gate["session_hash"] = getattr(request, "session_hash", None)
                if name == "ChatPage.refresh_chat_file_list" and result:
                    gate["returned_ids"] = [row["id"] for row in result[0]]
                matched = gate
                break
        if matched is not None:
            if not matched["release"].wait(timeout=40):
                raise RuntimeError("Owned file-browser barrier was not released")
            with self.lock:
                matched["completed"] = True

"""Deterministic model boundaries for the real submission browser fixture."""

import sys
import time
from pathlib import Path
from threading import Event, Lock, get_ident
from uuid import uuid4

from kotaemon.base import DocumentWithEmbedding, LLMInterface
from kotaemon.embeddings.base import BaseEmbeddings
from kotaemon.llms import ChatLLM

held_started = Event()
held_release = Event()
held_finished = Event()
generator_finished = Event()
held_times: dict[str, float] = {}
stream_lock = Lock()
streams: dict[str, dict] = {}
stream_generators: dict = {}
embedding_started = Event()
embedding_release = Event()
deletion_embedding_started = Event()
deletion_embedding_release = Event()


class SubmissionChatModel(ChatLLM):
    def invoke(self, messages, **kwargs):
        prompt = str(messages[-1])
        text = "Owned document discussion" if "conversation name" in prompt else "1"
        if "conversation name" in prompt and "ISOLATED CONVERSATION" in str(messages):
            text = "Isolated conversation"
        return LLMInterface(content=text, logprobs=[])

    def stream(self, messages, **kwargs):
        prompt = "\n".join(str(message) for message in messages)
        key = uuid4().hex
        with stream_lock:
            streams[key] = {
                "thread": get_ident(),
                "started": time.monotonic(),
                "finished": None,
                "held": "HELD_STREAM" in prompt,
            }
            iterator = _model_stream(prompt, key)
            stream_generators[key] = iterator
        return iterator


def _model_stream(prompt, key):
    try:
        yield LLMInterface(content="The owned document says ", logprobs=[])
        time.sleep(0.8)
        if "STREAM_FAILURE" in prompt:
            raise ValueError("Owned model stream failure")
        if "SLOW_STREAM" in prompt:
            time.sleep(4)
        if "HELD_STREAM" in prompt:
            held_times["started"] = time.monotonic()
            held_started.set()
            try:
                # Only explicit release or owned App teardown ends this wait.
                held_release.wait()
            finally:
                held_times["finished"] = time.monotonic()
                held_finished.set()
        yield LLMInterface(content="the observatory has seven telescopes.", logprobs=[])
    finally:
        with stream_lock:
            streams[key]["finished"] = time.monotonic()
        if "HELD_STREAM" in prompt:
            generator_finished.set()


def stream_snapshot():
    with stream_lock:
        return {
            key: {**value, "executing": stream_generators[key].gi_running}
            for key, value in streams.items()
        }


def worker_snapshot():
    frames = sys._current_frames()
    project = str(Path(__file__).resolve().parents[3]).replace("\\", "/").lower()
    workers = {}
    for stream in stream_snapshot().values():
        ident = stream["thread"]
        frame = frames.get(ident)
        active = []
        while frame is not None:
            filename = frame.f_code.co_filename.replace("\\", "/").lower()
            if filename.startswith(project + "/"):
                active.append({"file": filename, "function": frame.f_code.co_name})
            frame = frame.f_back
        workers[str(ident)] = {"alive": ident in frames, "project_frames": active}
    return workers


def close_idle_streams():
    """Caller first proves all requests and producer workers are idle."""
    for key, state in stream_snapshot().items():
        if state["finished"] is None and not state["executing"]:
            stream_generators[key].close()
            with stream_lock:
                streams[key]["closed_by_teardown"] = True
                streams[key]["finished"] = time.monotonic()


class SubmissionEmbeddings(BaseEmbeddings):
    def invoke(self, text, **kwargs):
        documents = self.prepare_input(text)
        combined = "\n".join(str(doc) for doc in documents)
        if "R5B_FAIL_EMBEDDING" in combined:
            raise ValueError("Owned R5-B embedding failure")
        if "R5B_HELD_EMBEDDING" in combined:
            embedding_started.set()
            if not embedding_release.wait(45):
                raise TimeoutError("Owned browser did not release embedding")
        if "R5B_DELETE_HELD" in combined:
            deletion_embedding_started.set()
            if not deletion_embedding_release.wait(90):
                raise TimeoutError("Owned browser did not release deletion embedding")
        return [
            DocumentWithEmbedding(content=doc, embedding=[1.0, 0.0, 0.0])
            for doc in documents
        ]

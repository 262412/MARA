"""Deterministic model boundaries for the real submission browser fixture."""

import time
from threading import Event

from kotaemon.base import DocumentWithEmbedding, LLMInterface
from kotaemon.embeddings.base import BaseEmbeddings
from kotaemon.llms import ChatLLM

held_started = Event()
held_release = Event()


class SubmissionChatModel(ChatLLM):
    def invoke(self, messages, **kwargs):
        prompt = str(messages[-1])
        text = "Owned document discussion" if "conversation name" in prompt else "1"
        if "conversation name" in prompt and "ISOLATED CONVERSATION" in str(messages):
            text = "Isolated conversation"
        return LLMInterface(content=text, logprobs=[])

    def stream(self, messages, **kwargs):
        prompt = "\n".join(str(message) for message in messages)
        yield LLMInterface(content="The owned document says ", logprobs=[])
        time.sleep(0.8)
        if "STREAM_FAILURE" in prompt:
            raise ValueError("Owned model stream failure")
        if "SLOW_STREAM" in prompt:
            time.sleep(4)
        if "HELD_STREAM" in prompt:
            held_started.set()
            if not held_release.wait(45):
                raise TimeoutError("Owned browser did not release the model boundary")
        yield LLMInterface(content="the observatory has seven telescopes.", logprobs=[])


class SubmissionEmbeddings(BaseEmbeddings):
    def invoke(self, text, **kwargs):
        return [
            DocumentWithEmbedding(content=doc, embedding=[1.0, 0.0, 0.0])
            for doc in self.prepare_input(text)
        ]

"""Deterministic model boundaries for the real submission browser fixture."""

import time

from kotaemon.base import DocumentWithEmbedding, LLMInterface
from kotaemon.embeddings.base import BaseEmbeddings
from kotaemon.llms import ChatLLM


class SubmissionChatModel(ChatLLM):
    def invoke(self, messages, **kwargs):
        prompt = str(messages[-1])
        text = "Owned document discussion" if "conversation name" in prompt else "1"
        return LLMInterface(content=text, logprobs=[])

    def stream(self, messages, **kwargs):
        prompt = "\n".join(str(message) for message in messages)
        yield LLMInterface(content="The owned document says ", logprobs=[])
        time.sleep(0.8)
        if "STREAM_FAILURE" in prompt:
            raise ValueError("Owned model stream failure")
        if "SLOW_STREAM" in prompt:
            time.sleep(4)
        yield LLMInterface(content="the observatory has seven telescopes.", logprobs=[])


class SubmissionEmbeddings(BaseEmbeddings):
    def invoke(self, text, **kwargs):
        return [
            DocumentWithEmbedding(content=doc, embedding=[1.0, 0.0, 0.0])
            for doc in self.prepare_input(text)
        ]

"""Observe input/output without changing model requests or generated chunks."""

from functools import wraps

from kotaemon.llms.chats.openai import BaseChatOpenAI

CALLS = []
original_stream = BaseChatOpenAI.stream
original_invoke = BaseChatOpenAI.invoke


def begin_call(model, method, messages, kwargs):
    record = {
        "method": method,
        "configured_model": model.model,
        "base_url": model.base_url,
        "temperature": model.temperature,
        "messages": model.prepare_message(messages),
        "kwargs": kwargs,
        "text": "",
        "complete": False,
    }
    CALLS.append(record)
    return record


@wraps(original_stream)
def observed_stream(self, messages, *args, **kwargs):
    record = begin_call(self, "stream", messages, kwargs)
    for chunk in original_stream(self, messages, *args, **kwargs):
        record["text"] += str(chunk.content or "")
        yield chunk
    record["complete"] = True


@wraps(original_invoke)
def observed_invoke(self, messages, *args, **kwargs):
    record = begin_call(self, "invoke", messages, kwargs)
    response = original_invoke(self, messages, *args, **kwargs)
    record["text"] = str(response.content or "")
    record["complete"] = True
    return response


BaseChatOpenAI.stream = observed_stream
BaseChatOpenAI.invoke = observed_invoke

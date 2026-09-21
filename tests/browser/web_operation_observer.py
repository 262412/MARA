"""Correlate only the owned harness's file/group callbacks with queue events."""

import asyncio
import hashlib
import inspect
import json
from contextvars import ContextVar
from typing import Any

current_operation: ContextVar[dict[str, Any]] = ContextVar(
    "owned_web_operation", default={}
)


def _plain(value):
    if hasattr(value, "get_config"):
        value = value.get_config()
    return json.loads(json.dumps(value, default=str))


def bind_operation_observer(blocks, chat_page, barriers):
    manager = getattr(chat_page._app, f"_index_{chat_page.file_index.id}")
    group_outputs = {manager.selected_group_id._id, manager.group_list_state._id}
    group_functions = {
        "interact_group_list",
        "list_group",
        "save_group",
        "delete_group",
        "set_group_id_selector",
    }
    records: list[dict[str, Any]] = []
    by_event: dict[str, dict[str, Any]] = {}
    _bind_application_observer(blocks, manager, records, by_event)
    original = blocks.call_function
    signature = inspect.signature(original)

    async def call_function(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        values = bound.arguments
        fn = values["block_fn"]
        if isinstance(fn, int):
            fn = blocks.fns[fn]
        is_files = fn.name == "refresh_chat_file_list"
        is_group = fn.name in group_functions or group_outputs.intersection(
            component._id for component in fn.outputs
        )
        if not (is_files or is_group):
            return await original(*args, **kwargs)
        request = values["requests"]
        if isinstance(request, list):
            request = request[0]
        inputs = values["processed_input"]
        record = {
            "event_id": values["event_id"],
            "fn": fn._id,
            "name": fn.name,
            "session_hash": getattr(request, "session_hash", None),
            "username": getattr(request, "username", None),
            "inputs": _file_inputs(inputs) if is_files else _plain(inputs),
            "outputs": [component._id for component in fn.outputs],
        }
        records.append({**record, "phase": "call"})
        by_event[record["event_id"]] = record
        token = current_operation.set(record)
        try:
            if is_group:
                await asyncio.to_thread(
                    barriers.observe, "WebOperation", "call", {"request": request}, None
                )
            result = await original(*args, **kwargs)
            prediction = result["prediction"]
            records.append(
                {
                    **record,
                    "phase": "return",
                    "result": (
                        _file_result(prediction) if is_files else _plain(prediction)
                    ),
                }
            )
            return result
        except BaseException as error:
            records.append({**record, "phase": "error", "error": type(error).__name__})
            raise
        finally:
            current_operation.reset(token)

    blocks.call_function = call_function
    return records


def _bind_application_observer(blocks, manager, records, by_event):
    original = blocks.process_api
    signature = inspect.signature(original)

    async def process_api(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        result = await original(*args, **kwargs)
        record = by_event.get(bound.arguments["event_id"])
        if record is not None:
            state = bound.arguments["state"]
            groups = state[manager.group_list_state._id]
            records.append(
                {
                    **record,
                    "phase": "postprocess",
                    "selected_group_id": state[manager.selected_group_id._id],
                    "group_list_version": hashlib.sha256(
                        json.dumps(groups, sort_keys=True).encode()
                    ).hexdigest(),
                    "group_ids": [group["id"] for group in groups],
                }
            )
        return result

    blocks.process_api = process_api


def _file_inputs(inputs):
    return dict(
        zip(
            (
                "conversation",
                "user_id",
                "choices",
                "selected",
                "graph_ids",
                "filter",
                "stamp",
            ),
            _plain(inputs),
        )
    )


def _file_result(payload):
    outputs = payload["outputs"]
    return {
        **{
            key: payload[key] for key in ("stamp", "conversation", "selected", "filter")
        },
        "ids": [row["id"] for row in outputs[0]],
        "display_sha256": [
            hashlib.sha256(str(value).encode()).hexdigest() for value in outputs[1:]
        ],
    }

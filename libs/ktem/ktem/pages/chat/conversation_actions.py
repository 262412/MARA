"""Adapt authorized session records and index defaults to conversation outputs.

Authentication, service calls and their exception boundaries stay in the control.
These functions only assemble the existing Web output slots, retaining references.
"""

_DEFAULT_SELECTION = object()


def empty_conversation_outputs(default_suggestions, default_state):
    return ("", "", "", [], default_suggestions, "", None, [], [], False, default_state)


def selected_conversation_outputs(session_info, user_id, default_suggestions):
    id_ = session_info.conversation_id
    name = session_info.name
    is_public = session_info.is_public
    selected = session_info.selected_mapping if user_id == session_info.user_id else {}
    chats = session_info.data_source.get("messages", [])
    suggestions = session_info.data_source.get("chat_suggestions", default_suggestions)
    retrieval_history = session_info.retrieval_messages
    plot_history = session_info.plot_history
    info = (
        retrieval_history[-1]
        if retrieval_history
        else "<h5><b>No evidence found.</b></h5>"
    )
    plot = plot_history[-1] if plot_history else None
    state = session_info.state
    return (
        id_,
        id_,
        name,
        chats,
        suggestions,
        info,
        plot,
        retrieval_history,
        plot_history,
        is_public,
        state,
    ), selected


def selector_outputs(indices, selected=_DEFAULT_SELECTION):
    outputs = []
    for index in indices:
        if index.selector is None:
            continue
        if isinstance(index.selector, int):
            outputs.append(_selector_value(index, selected))
        if isinstance(index.selector, tuple):
            outputs.extend(_selector_value(index, selected))
    return outputs


def _selector_value(index, selected):
    if selected is _DEFAULT_SELECTION:
        return index.default_selector
    # Keep the original eager default lookup, even when the mapping has this ID.
    return selected.get(str(index.id), index.default_selector)

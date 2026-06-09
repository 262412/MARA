from __future__ import annotations

from typing import Any

BRIEFING_FORMATS = {
    "executive_brief": {
        "label": "Executive Brief",
        "description": "Concise leadership brief with context, key findings, risks, and recommended next steps.",
        "instruction": (
            "Create an executive brief with sections for context, key findings, "
            "risks, recommendations, and cited source evidence."
        ),
    },
    "decision_memo": {
        "label": "Decision Memo",
        "description": "Decision-ready memo focused on options, tradeoffs, recommendation, and evidence.",
        "instruction": (
            "Create a decision memo that states the decision, compares options, "
            "explains tradeoffs, recommends a path, and cites source evidence."
        ),
    },
    "research_brief": {
        "label": "Research Brief",
        "description": "Source-grounded research brief with background, synthesis, evidence, and open questions.",
        "instruction": (
            "Create a research brief with background, evidence synthesis, "
            "important citations, and open questions."
        ),
    },
}

SLIDE_DECK_FORMATS = {
    "detailed_deck": (
        "Detailed Presentation",
        "A complete presentation with full text and details, suitable for email or standalone reading.",
    ),
    "presentation_slides": (
        "Presentation Slides",
        "Concise visual slides with speaker support points for live presentation.",
    ),
}


def artifact_parameter_state(artifact_type: str) -> dict[str, dict[str, Any]]:
    normalized_type = _normalized_type(artifact_type)
    state = _base_state()
    if normalized_type == "study_guide":
        _study_guide_state(state)
    elif normalized_type in {"quiz", "flashcards", "faq"}:
        _quantity_artifact_state(state, normalized_type)
    elif normalized_type == "briefing_doc":
        _briefing_doc_state(state)
    elif normalized_type == "infographic":
        _infographic_state(state)
    elif normalized_type == "slide_deck":
        _slide_deck_state(state)
    elif normalized_type == "audio_overview":
        _audio_overview_state(state)
    elif normalized_type == "video_overview":
        _video_overview_state(state)
    else:
        state["prompt"]["visible"] = True
    return state


def dependent_parameter_updates(
    artifact_type: str,
    format_value: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_type = _normalized_type(artifact_type)
    format_key = str(format_value or "").strip()
    prompt_update = {
        "visible": artifact_parameter_state(normalized_type)["prompt"]["visible"]
    }
    explanation_update = {"visible": False, "value": ""}
    if normalized_type == "study_guide":
        prompt_update = {
            "visible": format_key == "custom",
            "label": "Custom style prompt",
            "placeholder": "Example: Use a PhD seminar tone; pretend to be an RPG host.",
        }
    elif normalized_type == "briefing_doc":
        explanation_update = {
            "visible": True,
            "value": _briefing_explanation(format_key or "executive_brief"),
        }
    elif normalized_type == "slide_deck":
        explanation_update = {
            "visible": True,
            "value": _slide_deck_explanation(format_key or "detailed_deck"),
        }
    return prompt_update, explanation_update


def build_parameterized_artifact_prompt(
    artifact_type: str,
    *,
    prompt: str = "",
    output_format: str = "",
    difficulty: str = "",
    count: Any = None,
    language: str | None = None,
    note_records: list[dict[str, Any]] | None = None,
) -> str:
    normalized_type = _normalized_type(artifact_type)
    parts = [_base_instruction(normalized_type, prompt, output_format)]
    parts.extend(_parameter_lines(normalized_type, output_format, difficulty, count))
    language_text = str(language or "").strip()
    if language_text:
        parts.append(f"Language: {language_text}.")
    if note_records:
        parts.append("Notebook notes:")
        parts.extend(_note_prompt_lines(note_records))
    return "\n".join(item for item in parts if item)


def _base_state() -> dict[str, dict[str, Any]]:
    return {
        "prompt": {
            "visible": False,
            "label": "User prompt",
            "placeholder": "Describe what this artifact should focus on.",
        },
        "format": {"visible": False, "label": "Format", "choices": [], "value": ""},
        "difficulty": {"visible": False, "label": "Option", "choices": [], "value": ""},
        "count": {"visible": False, "label": "Quantity", "choices": [], "value": ""},
        "format_explanation": {"visible": False, "value": ""},
    }


def _show_field(
    field: dict[str, Any],
    *,
    label: str,
    choices: list[str],
    value: str,
) -> None:
    field.update({"visible": True, "label": label, "choices": choices, "value": value})


def _study_guide_state(state: dict[str, dict[str, Any]]) -> None:
    _show_field(
        state["format"],
        label="Goal, style, or role",
        choices=["default", "study_guide", "custom"],
        value="default",
    )
    state["prompt"].update(
        {
            "visible": False,
            "label": "Custom style prompt",
            "placeholder": "Example: Use a PhD seminar tone; pretend to be an RPG host.",
        }
    )


def _quantity_artifact_state(
    state: dict[str, dict[str, Any]],
    artifact_type: str,
) -> None:
    state["prompt"]["visible"] = True
    label = "Card count" if artifact_type == "flashcards" else "Question count"
    _show_field(
        state["count"],
        label=label,
        choices=["fewer", "default", "more"],
        value="default",
    )


def _briefing_doc_state(state: dict[str, dict[str, Any]]) -> None:
    _show_field(
        state["format"],
        label="Briefing format",
        choices=list(BRIEFING_FORMATS),
        value="executive_brief",
    )
    state["format_explanation"].update(
        {"visible": True, "value": _briefing_explanation("executive_brief")}
    )


def _infographic_state(state: dict[str, dict[str, Any]]) -> None:
    state["prompt"]["visible"] = True
    _show_field(
        state["format"],
        label="Screen orientation",
        choices=["portrait", "landscape", "square"],
        value="landscape",
    )
    _show_field(
        state["difficulty"],
        label="Visual style",
        choices=["clean_editorial", "dashboard", "academic_poster"],
        value="clean_editorial",
    )
    _show_field(
        state["count"],
        label="Detail level",
        choices=["concise", "default", "detailed"],
        value="default",
    )


def _slide_deck_state(state: dict[str, dict[str, Any]]) -> None:
    state["prompt"]["visible"] = True
    _show_field(
        state["format"],
        label="Deck format",
        choices=list(SLIDE_DECK_FORMATS),
        value="detailed_deck",
    )
    state["format_explanation"].update(
        {"visible": True, "value": _slide_deck_explanation("detailed_deck")}
    )


def _audio_overview_state(state: dict[str, dict[str, Any]]) -> None:
    state["prompt"]["visible"] = True
    _show_field(
        state["format"],
        label="Audio format",
        choices=["conversational_overview", "lecture_briefing", "podcast_summary"],
        value="conversational_overview",
    )
    _show_field(
        state["difficulty"],
        label="Duration",
        choices=["short", "default", "long"],
        value="default",
    )


def _video_overview_state(state: dict[str, dict[str, Any]]) -> None:
    state["prompt"]["visible"] = True
    _show_field(
        state["format"],
        label="Video format",
        choices=["explainer", "lecture_walkthrough", "executive_briefing"],
        value="explainer",
    )
    _show_field(
        state["difficulty"],
        label="Visual style",
        choices=["clean_slides", "whiteboard", "documentary"],
        value="clean_slides",
    )


def _base_instruction(
    artifact_type: str,
    prompt: str,
    output_format: str,
) -> str:
    user_prompt = str(prompt or "").strip()
    if artifact_type == "study_guide":
        if output_format == "custom":
            custom = user_prompt or "Use a clear expert learning style."
            return (
                "Create a source-grounded study guide.\n"
                f"Custom study guide style or role: {custom}."
            )
        if output_format == "study_guide":
            return "Create a structured source-grounded study guide for learning and review."
        return "Create a source-grounded study guide."
    if artifact_type == "briefing_doc":
        selected = (
            BRIEFING_FORMATS.get(output_format) or BRIEFING_FORMATS["executive_brief"]
        )
        return f"{selected['label']}: {selected['instruction']}"
    defaults = {
        "quiz": "Create a source-grounded quiz.",
        "flashcards": "Create source-grounded flashcards.",
        "mindmap": "Create an interactive source-grounded mind map.",
        "slide_outline": "Create a source-grounded slide outline.",
        "faq": "Create a source-grounded FAQ.",
        "timeline": "Create a source-grounded timeline.",
        "data_table": "Create a source-grounded data table.",
        "infographic": "Create a source-grounded infographic plan.",
        "slide_deck": "Create a source-grounded slide deck plan.",
        "audio_overview": "Create a source-grounded audio overview script.",
        "video_overview": "Create a source-grounded video overview plan.",
    }
    return user_prompt or defaults.get(
        artifact_type, "Generate a source-grounded artifact."
    )


def _parameter_lines(
    artifact_type: str,
    output_format: str,
    difficulty: str,
    count: Any,
) -> list[str]:
    if artifact_type == "quiz":
        return [f"Question count: {_option(count, 'default')}."]
    if artifact_type == "flashcards":
        return [f"Card count: {_option(count, 'default')}."]
    if artifact_type == "faq":
        return [f"Question count: {_option(count, 'default')}."]
    if artifact_type == "infographic":
        return [
            f"Screen orientation: {_option(output_format, 'landscape')}.",
            f"Visual style: {_option(difficulty, 'clean_editorial')}.",
            f"Detail level: {_option(count, 'default')}.",
        ]
    if artifact_type == "slide_deck":
        label, description = SLIDE_DECK_FORMATS.get(
            str(output_format or ""), SLIDE_DECK_FORMATS["detailed_deck"]
        )
        return [f"Deck format: {label} - {description}"]
    if artifact_type == "audio_overview":
        return [
            f"Audio format: {_option(output_format, 'conversational_overview')}.",
            f"Duration: {_option(difficulty, 'default')}.",
        ]
    if artifact_type == "video_overview":
        return [
            f"Video format: {_option(output_format, 'explainer')}.",
            f"Visual style: {_option(difficulty, 'clean_slides')}.",
        ]
    return []


def _briefing_explanation(format_key: str) -> str:
    selected = BRIEFING_FORMATS.get(format_key) or BRIEFING_FORMATS["executive_brief"]
    return f"**{selected['label']}**\n\n{selected['description']}"


def _slide_deck_explanation(format_key: str) -> str:
    label, description = SLIDE_DECK_FORMATS.get(
        format_key,
        SLIDE_DECK_FORMATS["detailed_deck"],
    )
    return f"**{label}**\n\n{description}"


def _normalized_type(value: Any) -> str:
    artifact_type = str(value or "study_guide").strip()
    return "briefing_doc" if artifact_type == "custom_report" else artifact_type


def _option(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text or fallback


def _note_prompt_lines(note_records: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for note in note_records:
        note_id = str(note.get("note_id") or "").strip()
        title = str(note.get("title") or "Notebook note").strip()
        text = str(note.get("text") or "").strip()
        lines.append(f"- {title} ({note_id}): {text}")
    return lines

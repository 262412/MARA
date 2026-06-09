from ktem.pages.chat.studio_artifact_generation import (
    STUDIO_ARTIFACT_TYPE_CHOICES,
    build_studio_artifact_prompt,
)
from ktem.pages.chat.studio_artifact_parameters import (
    artifact_parameter_state,
    dependent_parameter_updates,
)


def test_studio_artifact_type_choices_merge_custom_report_into_briefing_doc():
    assert "briefing_doc" in STUDIO_ARTIFACT_TYPE_CHOICES
    assert "custom_report" not in STUDIO_ARTIFACT_TYPE_CHOICES


def test_mindmap_slide_outline_timeline_and_data_table_only_show_scope_and_prompt():
    for artifact_type in ["mindmap", "slide_outline", "timeline", "data_table"]:
        state = artifact_parameter_state(artifact_type)

        assert state["prompt"]["visible"] is True
        assert state["format"]["visible"] is False
        assert state["difficulty"]["visible"] is False
        assert state["count"]["visible"] is False
        assert state["format_explanation"]["visible"] is False


def test_study_guide_uses_style_role_selector_and_custom_prompt_dependency():
    state = artifact_parameter_state("study_guide")

    assert state["format"]["visible"] is True
    assert state["format"]["label"] == "Goal, style, or role"
    assert state["format"]["choices"] == ["default", "study_guide", "custom"]
    assert state["prompt"]["visible"] is False
    assert state["difficulty"]["visible"] is False
    assert state["count"]["visible"] is False

    prompt_update, explanation_update = dependent_parameter_updates(
        "study_guide", "custom"
    )
    assert prompt_update["visible"] is True
    assert "Custom style prompt" in prompt_update["label"]
    assert explanation_update["visible"] is False


def test_quiz_flashcards_and_faq_use_quantity_dropdowns():
    expected = {
        "quiz": "Question count",
        "flashcards": "Card count",
        "faq": "Question count",
    }
    for artifact_type, label in expected.items():
        state = artifact_parameter_state(artifact_type)

        assert state["count"]["visible"] is True
        assert state["count"]["label"] == label
        assert state["count"]["choices"] == ["fewer", "default", "more"]
        assert state["format"]["visible"] is False
        assert state["difficulty"]["visible"] is False


def test_briefing_doc_uses_format_templates_instead_of_user_prompt():
    state = artifact_parameter_state("briefing_doc")

    assert state["prompt"]["visible"] is False
    assert state["format"]["visible"] is True
    assert state["format"]["label"] == "Briefing format"
    assert state["format_explanation"]["visible"] is True
    assert "Executive Brief" in state["format_explanation"]["value"]

    prompt = build_studio_artifact_prompt(
        "briefing_doc",
        output_format="decision_memo",
        prompt="This should not be used as the main instruction.",
    )

    assert "Decision Memo" in prompt
    assert "This should not be used as the main instruction." not in prompt
    assert "Difficulty:" not in prompt
    assert "Requested item count:" not in prompt


def test_infographic_slide_deck_audio_and_video_have_specific_parameter_labels():
    infographic = artifact_parameter_state("infographic")
    assert infographic["format"]["label"] == "Screen orientation"
    assert infographic["difficulty"]["label"] == "Visual style"
    assert infographic["count"]["label"] == "Detail level"

    slide_deck = artifact_parameter_state("slide_deck")
    assert slide_deck["format"]["label"] == "Deck format"
    assert "Detailed Presentation" in slide_deck["format_explanation"]["value"]
    assert slide_deck["difficulty"]["visible"] is False
    assert slide_deck["count"]["visible"] is False

    audio = artifact_parameter_state("audio_overview")
    assert audio["format"]["label"] == "Audio format"
    assert audio["difficulty"]["label"] == "Duration"
    assert audio["count"]["visible"] is False

    video = artifact_parameter_state("video_overview")
    assert video["format"]["label"] == "Video format"
    assert video["difficulty"]["label"] == "Visual style"
    assert video["count"]["visible"] is False


def test_artifact_prompt_builder_uses_type_specific_quantity_and_style_language():
    quiz_prompt = build_studio_artifact_prompt(
        "quiz",
        prompt="Focus on terminology.",
        count="more",
        language="English",
    )
    assert "Question count: more." in quiz_prompt
    assert "Requested item count:" not in quiz_prompt

    guide_prompt = build_studio_artifact_prompt(
        "study_guide",
        output_format="custom",
        prompt="Use a PhD seminar tone.",
    )
    assert "Custom study guide style or role: Use a PhD seminar tone." in guide_prompt
    assert "Preferred format:" not in guide_prompt

from ktem.pages.chat.studio_artifact_picker import (
    select_studio_artifact_type_update,
    show_studio_artifact_picker_update,
)


def test_select_studio_artifact_type_opens_center_detail_without_hiding_cards():
    (
        selected,
        selector_update,
        backdrop_update,
        detail_update,
        title_html,
        prompt_update,
        format_update,
        difficulty_update,
        count_update,
        explanation_update,
        note_ids_update,
    ) = select_studio_artifact_type_update("quiz")

    assert selected == "quiz"
    assert selector_update["visible"] is True
    assert backdrop_update["visible"] is True
    assert detail_update["visible"] is True
    assert "Quiz" in title_html
    assert prompt_update["visible"] is True
    assert format_update["visible"] is False
    assert difficulty_update["visible"] is False
    assert count_update["visible"] is True
    assert count_update["label"] == "Question count"
    assert explanation_update["visible"] is False
    assert note_ids_update["visible"] is False


def test_show_studio_artifact_picker_closes_center_detail_panel():
    (
        selector_update,
        backdrop_update,
        detail_update,
    ) = show_studio_artifact_picker_update()

    assert selector_update["visible"] is True
    assert backdrop_update["visible"] is False
    assert detail_update["visible"] is False

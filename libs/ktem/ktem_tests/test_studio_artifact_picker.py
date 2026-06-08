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
    ) = select_studio_artifact_type_update("quiz")

    assert selected == "quiz"
    assert selector_update["visible"] is True
    assert backdrop_update["visible"] is True
    assert detail_update["visible"] is True
    assert "Quiz" in title_html


def test_show_studio_artifact_picker_closes_center_detail_panel():
    (
        selector_update,
        backdrop_update,
        detail_update,
    ) = show_studio_artifact_picker_update()

    assert selector_update["visible"] is True
    assert backdrop_update["visible"] is False
    assert detail_update["visible"] is False

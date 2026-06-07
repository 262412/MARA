from ktem.pages.chat.studio_artifacts import render_studio_artifacts_html


def test_studio_empty_state_lists_full_target_artifact_catalog():
    html = render_studio_artifacts_html()

    for label in [
        "Study Guide",
        "Quiz",
        "Flashcards",
        "Mind Map",
        "Reports",
        "Data Table",
        "Infographic",
        "Slide Deck",
        "Audio Overview",
        "Video Overview",
    ]:
        assert label in html

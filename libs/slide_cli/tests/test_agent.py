import json
from types import SimpleNamespace

from pptx import Presentation

from slide_cli.agent import SlideAgentRunner


def test_agent_runner_can_use_tool_before_final(monkeypatch, tmp_path):
    deck_path = tmp_path / "deck.pptx"

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "QBR"
    slide.placeholders[1].text = "Revenue is flat."
    presentation.save(deck_path)

    responses = [
        SimpleNamespace(
            text=json.dumps(
                {
                    "type": "tool",
                    "tool": "read_slide",
                    "input": "1",
                }
            )
        ),
        SimpleNamespace(
            text=json.dumps(
                {
                    "type": "final",
                    "assistant_response": "Reframed the title for executives.",
                    "patch": {
                        "summary": "Update slide title",
                        "edits": [
                            {
                                "slide_number": 1,
                                "target_id": "slide-1/shape-2/text",
                                "before_text": "QBR",
                                "after_text": "Executive QBR",
                            }
                        ],
                    },
                }
            )
        ),
    ]

    monkeypatch.setattr(
        "slide_cli.agent.run_completion",
        lambda **kwargs: responses.pop(0),
    )

    runner = SlideAgentRunner(
        input_path=str(deck_path),
        model="gpt-4o-mini",
        config_path="missing.yml",
        cwd=str(tmp_path),
    )
    result = runner.run("Rewrite the deck title for executives.")

    assert result["assistant_response"] == "Reframed the title for executives."
    assert result["patch"].summary == "Update slide title"
    assert result["patch"].edits[0].after_text == "Executive QBR"
    assert result["observations"]

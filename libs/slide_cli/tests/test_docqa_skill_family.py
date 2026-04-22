from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / ".codex" / "skills"


EXPECTED_SKILLS = {
    "slide-docqa": [
        "slide docqa doctor",
        "slide docqa index",
        "slide docqa files",
        "slide docqa delete",
        "slide docqa ask",
        "slide docqa chat",
        "slide docqa sessions",
        "slide docqa resume",
    ],
    "slide-docqa-ask": ["slide docqa ask"],
    "slide-docqa-chat": ["slide docqa chat"],
    "slide-docqa-doctor": ["slide docqa doctor"],
    "slide-docqa-delete": ["slide docqa delete"],
    "slide-docqa-files": ["slide docqa files"],
    "slide-docqa-index": ["slide docqa index"],
    "slide-docqa-resume": ["slide docqa resume"],
    "slide-docqa-sessions": ["slide docqa sessions"],
}


def _read_skill(skill_name: str) -> str:
    return (SKILL_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")


def test_slide_docqa_skill_family_is_anchored_to_grouped_mainline_commands():
    for skill_name, anchors in EXPECTED_SKILLS.items():
        text = _read_skill(skill_name)
        assert f"name: {skill_name}" in text
        for anchor in anchors:
            assert anchor in text, f"{skill_name} is missing canonical anchor: {anchor}"


def test_slide_docqa_skill_family_has_no_missing_files():
    expected_files = set(EXPECTED_SKILLS)
    actual_files = {
        path.name
        for path in SKILL_ROOT.iterdir()
        if path.is_dir()
        and path.name.startswith("slide-docqa")
        and (path / "SKILL.md").is_file()
    }

    assert actual_files == expected_files

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / ".codex" / "skills"


EXPECTED_SKILLS = {
    "MARA-docqa": [
        "MARA docqa doctor",
        "MARA docqa index",
        "MARA docqa files",
        "MARA docqa delete",
        "MARA docqa ask",
        "MARA docqa chat",
        "MARA docqa sessions",
        "MARA docqa notes",
        "MARA docqa sources",
        "MARA docqa artifacts",
        "MARA docqa resume",
    ],
    "MARA-docqa-artifacts": ["MARA docqa artifacts"],
    "MARA-docqa-ask": ["MARA docqa ask"],
    "MARA-docqa-chat": ["MARA docqa chat"],
    "MARA-docqa-doctor": ["MARA docqa doctor"],
    "MARA-docqa-delete": ["MARA docqa delete"],
    "MARA-docqa-files": ["MARA docqa files"],
    "MARA-docqa-index": ["MARA docqa index"],
    "MARA-docqa-notes": ["MARA docqa notes"],
    "MARA-docqa-resume": ["MARA docqa resume"],
    "MARA-docqa-sessions": ["MARA docqa sessions"],
    "MARA-docqa-sources": ["MARA docqa sources"],
}


def _read_skill(skill_name: str) -> str:
    return (SKILL_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")


def test_mara_docqa_skill_family_is_anchored_to_grouped_mainline_commands():
    for skill_name, anchors in EXPECTED_SKILLS.items():
        text = _read_skill(skill_name)
        assert f"name: {skill_name}" in text
        for anchor in anchors:
            assert anchor in text, f"{skill_name} is missing canonical anchor: {anchor}"


def test_mara_docqa_skill_family_has_no_missing_files():
    expected_files = set(EXPECTED_SKILLS)
    actual_files = {
        path.name
        for path in SKILL_ROOT.iterdir()
        if path.is_dir()
        and path.name.startswith("MARA-docqa")
        and (path / "SKILL.md").is_file()
    }

    assert actual_files == expected_files

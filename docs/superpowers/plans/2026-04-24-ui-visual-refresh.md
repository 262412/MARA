# UI Visual Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the Slides/Kotaemon Gradio UI with a precise research-workbench default theme, graph-lab dark-mode cues, and warmer document-reading surfaces.

**Architecture:** Keep all changes in the current Gradio theme and CSS layer. Add a focused asset-style regression test so future edits do not drift back into a single slate/blue-green treatment or remove the reading-surface variables.

**Tech Stack:** Python, pytest, Gradio theme tokens, CSS.

---

## File Structure

- Create: `libs/ktem/ktem_tests/test_assets_theme.py`
  - Verifies approved theme and CSS contracts.
- Modify: `libs/ktem/ktem/assets/theme.py`
  - Tunes Gradio theme colors, gradients, neutral hues, input/button/table tokens, and font defaults.
- Modify: `libs/ktem/ktem/assets/css/main.css`
  - Adds semantic UI color variables, updates global surfaces, tabs, chat, preview, citation/evidence cards, and knowledge graph wrappers.

## Tasks

### Task 1: Add Style Contract Tests

- [ ] Create `libs/ktem/ktem_tests/test_assets_theme.py` with tests that read `theme.py` and `main.css`.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest libs\ktem\ktem_tests\test_assets_theme.py -q` and confirm failure because the new CSS variables are not present yet.

### Task 2: Update Theme Tokens

- [ ] Modify `libs/ktem/ktem/assets/theme.py` so the default theme uses teal primary, blue secondary, calmer slate neutrals, and Plus Jakarta Sans.
- [ ] Keep dark mode readable by using deep navy/slate surfaces and mint/cyan accents.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest libs\ktem\ktem_tests\test_assets_theme.py -q` and confirm remaining failures point to CSS variables only.

### Task 3: Update App CSS Surfaces

- [ ] Modify `libs/ktem/ktem/assets/css/main.css` to introduce semantic variables for app background, surfaces, elevated panels, accent, focus, reading surface, graph dark surface, shadows, and borders.
- [ ] Apply those variables to tabs, panels, chat bubbles, document preview, citation/evidence hints, and knowledge graph wrappers.
- [ ] Avoid decorative orb or bokeh backgrounds.

### Task 4: Verify

- [ ] Run `.\.venv\Scripts\python.exe -m pytest libs\ktem\ktem_tests\test_assets_theme.py -q`.
- [ ] Run a syntax/import check for the theme file with `.\.venv\Scripts\python.exe -m py_compile libs\ktem\ktem\assets\theme.py`.
- [ ] Launch the app and inspect it in the in-app browser.

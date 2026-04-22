# Knowledge Graph Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inline knowledge graph with a preview card that opens a fullscreen viewer supporting drag-to-pan, wheel zoom, toolbar zoom controls, and existing node-click prompt filling.

**Architecture:** Keep the knowledge graph schema and HTML branch renderer intact, but wrap the rendered graph in a preview-card and overlay-viewer shell. Put pan/zoom math in a standalone JavaScript helper that can be unit-tested with Node, then wire the overlay lifecycle and node click preservation through `main.js`.

**Tech Stack:** Python, Gradio HTML rendering, existing `KnowledgeGraphRenderer`, browser JavaScript, Node built-in test runner, pytest, CSS.

---

## File Structure

**Modify**

- `D:\PythonProject\kotaemon\libs\ktem\ktem\pages\chat\knowledge_graph_renderer.py`
  - Replace the direct inline mind map wrapper with preview-card and fullscreen-viewer markup while preserving node payload attributes.
- `D:\PythonProject\kotaemon\libs\ktem\ktem\assets\js\main.js`
  - Bind preview-card open/close, fullscreen viewer state, drag and zoom interactions, and preserve node click prompt filling.
- `D:\PythonProject\kotaemon\libs\ktem\ktem\assets\css\main.css`
  - Style the preview card, fullscreen overlay, viewer controls, viewport, stage, and responsive behavior.
- `D:\PythonProject\kotaemon\libs\ktem\ktem\app.py`
  - Load the standalone viewer helper before `main.js` so browser runtime and tests use the same functions.
- `D:\PythonProject\kotaemon\libs\ktem\ktem_tests\test_knowledge_graph_service.py`
  - Add renderer contract tests for preview-card, fullscreen overlay shell, split-map metadata, and non-ready card states.

**Create**

- `D:\PythonProject\kotaemon\libs\ktem\ktem\assets\js\knowledge_graph_viewer.js`
  - Export pure helper functions for fit, zoom, clamp, and drag-threshold calculations and attach them to `globalThis`.
- `D:\PythonProject\kotaemon\libs\ktem\ktem\assets\js\knowledge_graph_viewer.test.js`
  - Unit-test the pan/zoom math with Node's built-in `node:test` runner.

## Task 1: Wrap Ready Graphs In A Preview Card And Fullscreen Viewer Shell

**Files:**

- Modify: `D:\PythonProject\kotaemon\libs\ktem\ktem_tests\test_knowledge_graph_service.py`
- Modify: `D:\PythonProject\kotaemon\libs\ktem\ktem\pages\chat\knowledge_graph_renderer.py`

- [ ] **Step 1: Write the failing renderer contract test**

```python
def test_render_graph_html_wraps_ready_graph_in_preview_card_and_viewer(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)
    graph = {
        "schema_version": 2,
        "source_ids": ["file-a", "file-b"],
        "maps": [
            {
                "id": "map::1",
                "type": "knowledge_map",
                "kind": "map",
                "label": "Knowledge System 1",
                "summary": "Connected source set.",
                "related_file_ids": ["file-a", "file-b"],
                "component_ids": ["component::1"],
                "support_pages": {"file-a": ["1"], "file-b": ["2"]},
                "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
            }
        ],
        "components": [
            {
                "id": "component::1",
                "type": "component",
                "kind": "component",
                "label": "Component 1",
                "summary": "Shared concepts",
                "related_file_ids": ["file-a", "file-b"],
                "support_pages": {"file-a": ["1"], "file-b": ["2"]},
                "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
                "children": [],
            }
        ],
        "themes": [],
        "subthemes": [],
        "knowledge_points": [],
        "node_index": {
            "component::1": {
                "id": "component::1",
                "type": "component",
                "kind": "component",
                "label": "Component 1",
                "summary": "Shared concepts",
                "related_file_ids": ["file-a", "file-b"],
                "support_pages": {"file-a": ["1"], "file-b": ["2"]},
                "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
                "children": [],
            }
        },
        "support_pages": {"file-a": ["1"], "file-b": ["2"]},
        "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
    }

    rendered = service._render_graph_html(graph, focus_file_id="", status="ready")

    assert "kg-preview-card" in rendered
    assert "data-kg-open-viewer='true'" in rendered
    assert "kg-viewer-overlay" in rendered
    assert "kg-viewer-viewport" in rendered
    assert "kg-viewer-stage" in rendered
    assert "Component 1" in rendered
```

- [ ] **Step 2: Run the targeted pytest and verify it fails for the expected reason**

Run: `.\.venv\Scripts\python.exe -m pytest libs\ktem\ktem_tests\test_knowledge_graph_service.py -k "preview_card_and_viewer" -q`

Expected: `FAIL` because the current renderer still returns `.kg-mindmap-root` directly and does not emit `kg-preview-card` or `kg-viewer-overlay`.

- [ ] **Step 3: Implement the preview-card and viewer shell in the renderer**

```python
def _render_graph_canvas(self, graph: dict[str, Any], focus_file_id: str) -> str:
    maps = self._graph_maps(graph)
    root_source_ids = list(graph.get("source_ids", []) or [])
    shell_html: list[str] = []
    if len(maps) == 1:
        single_root = self._materialize_v2_item(
            {
                "id": "root::conversation",
                "type": "knowledge_root",
                "kind": "root",
                "label": "Conversation Knowledge Map",
                "summary": "Horizontal mind map organized as component, theme, subtheme, and knowledge point branches.",
                "related_file_ids": root_source_ids,
                "support_pages": graph.get("support_pages", {}) or {},
                "support_chunk_ids": graph.get("support_chunk_ids", {}) or {},
                "component_ids": list(maps[0].get("component_ids", []) or []),
            },
            graph,
            "knowledge_root",
        )
        shell_html.append("<div class='kg-mindmap-root'>")
        shell_html.append(self._render_branch(single_root, focus_file_id, "knowledge_root", 0))
        shell_html.append("</div>")
        return "".join(shell_html)
    shell_html.append("<div class='kg-mindmap-root kg-mindmap-root--split'>")
    shell_html.append("</div>")
    return "".join(shell_html)


def _render_preview_card(self, graph: dict[str, Any], maps: list[dict[str, Any]], status: str) -> str:
    title = "Conversation Knowledge Map" if len(maps) <= 1 else "Conversation Knowledge Maps"
    source_count = len(graph.get("source_ids", []) or [])
    meta = (
        f"Split into {len(maps)} separate maps"
        if len(maps) > 1
        else f"Based on {source_count} sources"
    )
    return (
        "<button type='button' class='kg-preview-card' data-kg-open-viewer='true'>"
        f"<span class='kg-preview-card__title'>{html.escape(title)}</span>"
        f"<span class='kg-preview-card__meta'>{html.escape(meta)}</span>"
        "<span class='kg-preview-card__cta'>Open Graph</span>"
        "</button>"
    )


def render_graph_html(self, graph: dict[str, Any], focus_file_id: str, status: str) -> str:
    maps = self._graph_maps(graph)
    canvas_html = self._render_graph_canvas(graph, focus_file_id)
    return (
        "<div class='knowledge-graph-shell' id='knowledge-graph-panel' "
        f"data-kg-status='{html.escape(status, quote=True)}' data-kg-layout='mindmap' data-kg-schema='v2'>"
        f"{self._render_preview_card(graph, maps, status)}"
        "<div class='kg-viewer-overlay' data-kg-viewer-overlay='true' hidden>"
        "<div class='kg-viewer-dialog'>"
        "<div class='kg-viewer-toolbar'>"
        "<button type='button' data-kg-viewer-action='zoom-in'>+</button>"
        "<button type='button' data-kg-viewer-action='zoom-out'>-</button>"
        "<button type='button' data-kg-viewer-action='fit'>Fit</button>"
        "<button type='button' data-kg-viewer-action='reset'>Reset</button>"
        "<button type='button' data-kg-viewer-close='true'>Close</button>"
        "</div>"
        "<div class='kg-viewer-viewport' data-kg-viewer-viewport='true'>"
        f"<div class='kg-viewer-stage' data-kg-viewer-stage='true'>{canvas_html}</div>"
        "</div></div></div></div>"
    )
```

- [ ] **Step 4: Re-run the targeted pytest until it passes**

Run: `.\.venv\Scripts\python.exe -m pytest libs\ktem\ktem_tests\test_knowledge_graph_service.py -k "preview_card_and_viewer" -q`

Expected: `1 passed`.

- [ ] **Step 5: Commit the renderer shell milestone**

```bash
git add libs/ktem/ktem/pages/chat/knowledge_graph_renderer.py libs/ktem/ktem_tests/test_knowledge_graph_service.py
git commit -m "feat: add knowledge graph preview card shell"
```

## Task 2: Cover Split-State And Non-Ready Card Rendering

**Files:**

- Modify: `D:\PythonProject\kotaemon\libs\ktem\ktem_tests\test_knowledge_graph_service.py`
- Modify: `D:\PythonProject\kotaemon\libs\ktem\ktem\pages\chat\knowledge_graph_renderer.py`

- [ ] **Step 1: Add failing tests for split-map metadata and non-ready cards**

```python
def test_render_graph_html_shows_split_summary_on_preview_card(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)
    graph = {
        "schema_version": 2,
        "source_ids": ["file-a", "file-b"],
        "split_reason": "weakly_connected_sources",
        "maps": [
            {
                "id": "map::1",
                "type": "knowledge_map",
                "kind": "map",
                "label": "Map 1",
                "summary": "A",
                "related_file_ids": ["file-a"],
                "component_ids": [],
                "support_pages": {},
                "support_chunk_ids": {},
            },
            {
                "id": "map::2",
                "type": "knowledge_map",
                "kind": "map",
                "label": "Map 2",
                "summary": "B",
                "related_file_ids": ["file-b"],
                "component_ids": [],
                "support_pages": {},
                "support_chunk_ids": {},
            },
        ],
        "components": [],
        "themes": [],
        "subthemes": [],
        "knowledge_points": [],
        "node_index": {},
        "support_pages": {},
        "support_chunk_ids": {},
    }

    rendered = service._render_graph_html(graph, focus_file_id="", status="ready")

    assert "Split into 2 separate maps" in rendered
    assert "kg-map-split-banner" in rendered


def test_render_empty_html_uses_non_interactive_preview_card(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)

    rendered = service._render_empty_html(
        "No graph available yet.",
        "Upload related sources to generate a map.",
    )

    assert "kg-preview-card" in rendered
    assert "data-kg-open-viewer='false'" in rendered
    assert "No graph available yet." in rendered
```

- [ ] **Step 2: Run the targeted pytest and confirm the new assertions fail**

Run: `.\.venv\Scripts\python.exe -m pytest libs\ktem\ktem_tests\test_knowledge_graph_service.py -k "split_summary_on_preview_card or non_interactive_preview_card" -q`

Expected: `FAIL` because split summaries only appear inside the inline graph body and `render_empty_html()` still emits the legacy empty shell.

- [ ] **Step 3: Implement preview-card state variants in the renderer**

```python
def render_empty_html(self, message: str, hint: str = "") -> str:
    return (
        "<div class='knowledge-graph-shell' data-kg-status='empty' data-kg-layout='mindmap' data-kg-schema='v2'>"
        "<div class='kg-preview-card kg-preview-card--disabled' data-kg-open-viewer='false'>"
        f"<span class='kg-preview-card__title'>{html.escape(message)}</span>"
        f"<span class='kg-preview-card__meta'>{html.escape(hint)}</span>"
        "</div></div>"
    )


def _render_preview_card(self, graph: dict[str, Any], maps: list[dict[str, Any]], status: str) -> str:
    title = "Conversation Knowledge Map" if len(maps) <= 1 else "Conversation Knowledge Maps"
    source_count = len(graph.get("source_ids", []) or [])
    open_flag = "true" if status == "ready" else "false"
    disabled_class = "" if status == "ready" else " kg-preview-card--disabled"
    meta = (
        f"Split into {len(maps)} separate maps"
        if len(maps) > 1
        else f"Based on {source_count} sources"
    )
    return (
        f"<button type='button' class='kg-preview-card{disabled_class}' data-kg-open-viewer='{open_flag}'>"
        f"<span class='kg-preview-card__title'>{html.escape(title)}</span>"
        f"<span class='kg-preview-card__meta'>{html.escape(meta)}</span>"
        "<span class='kg-preview-card__cta'>Open Graph</span>"
        "</button>"
    )
```

- [ ] **Step 4: Re-run the renderer test subset and make sure it passes**

Run: `.\.venv\Scripts\python.exe -m pytest libs\ktem\ktem_tests\test_knowledge_graph_service.py -k "preview_card or split_summary_on_preview_card or non_interactive_preview_card" -q`

Expected: all targeted tests `PASS`.

- [ ] **Step 5: Commit the preview-state rendering changes**

```bash
git add libs/ktem/ktem/pages/chat/knowledge_graph_renderer.py libs/ktem/ktem_tests/test_knowledge_graph_service.py
git commit -m "feat: add knowledge graph preview card states"
```

## Task 3: Add Testable Pan/Zoom Math Helpers

**Files:**

- Create: `D:\PythonProject\kotaemon\libs\ktem\ktem\assets\js\knowledge_graph_viewer.test.js`
- Create: `D:\PythonProject\kotaemon\libs\ktem\ktem\assets\js\knowledge_graph_viewer.js`
- Modify: `D:\PythonProject\kotaemon\libs\ktem\ktem\app.py`

- [ ] **Step 1: Write failing Node tests for fit, clamp, zoom, and drag-threshold logic**

```javascript
const test = require("node:test");
const assert = require("node:assert/strict");
const viewer = require("./knowledge_graph_viewer.js");

test("computeFittedTransform centers content inside the viewport", () => {
  const result = viewer.computeFittedTransform({
    viewportWidth: 1200,
    viewportHeight: 800,
    contentWidth: 600,
    contentHeight: 400,
    padding: 40,
    minScale: 0.4,
    maxScale: 2.5,
  });

  assert.equal(result.scale, 1.8);
  assert.equal(Math.round(result.translateX), 60);
  assert.equal(Math.round(result.translateY), 40);
});

test("applyWheelZoom keeps the cursor anchor stable", () => {
  const result = viewer.applyWheelZoom(
    { scale: 1, translateX: 100, translateY: 50 },
    {
      deltaY: -120,
      cursorX: 300,
      cursorY: 200,
      minScale: 0.4,
      maxScale: 2.5,
      zoomStep: 0.14,
    }
  );

  assert.ok(result.scale > 1);
  assert.ok(result.translateX < 100);
  assert.ok(result.translateY < 50);
});

test("hasExceededDragThreshold ignores tiny pointer movement", () => {
  assert.equal(viewer.hasExceededDragThreshold(10, 10, 14, 13, 8), false);
  assert.equal(viewer.hasExceededDragThreshold(10, 10, 26, 18, 8), true);
});
```

- [ ] **Step 2: Run the Node test file and verify it fails because the helper module does not exist yet**

Run: `node --test libs/ktem/ktem/assets/js/knowledge_graph_viewer.test.js`

Expected: `FAIL` with module resolution errors for `knowledge_graph_viewer.js`.

- [ ] **Step 3: Implement the helper module and load it in the app**

```javascript
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
    return;
  }
  root.KnowledgeGraphViewerUtils = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function clampGraphScale(scale, minScale, maxScale) {
    return Math.max(minScale, Math.min(maxScale, scale));
  }

  function computeFittedTransform(options) {
    const availableWidth = Math.max(
      1,
      options.viewportWidth - options.padding * 2
    );
    const availableHeight = Math.max(
      1,
      options.viewportHeight - options.padding * 2
    );
    const fitScale = clampGraphScale(
      Math.min(
        availableWidth / options.contentWidth,
        availableHeight / options.contentHeight
      ),
      options.minScale,
      options.maxScale
    );
    return {
      scale: fitScale,
      translateX: (options.viewportWidth - options.contentWidth * fitScale) / 2,
      translateY:
        (options.viewportHeight - options.contentHeight * fitScale) / 2,
    };
  }

  function hasExceededDragThreshold(
    startX,
    startY,
    pointerX,
    pointerY,
    threshold
  ) {
    return (
      Math.abs(pointerX - startX) >= threshold ||
      Math.abs(pointerY - startY) >= threshold
    );
  }

  function applyWheelZoom(state, options) {
    const direction = options.deltaY < 0 ? 1 : -1;
    const nextScale = clampGraphScale(
      state.scale * (1 + direction * options.zoomStep),
      options.minScale,
      options.maxScale
    );
    const ratio = nextScale / state.scale;
    return {
      scale: nextScale,
      translateX:
        options.cursorX - (options.cursorX - state.translateX) * ratio,
      translateY:
        options.cursorY - (options.cursorY - state.translateY) * ratio,
    };
  }

  return {
    clampGraphScale,
    computeFittedTransform,
    hasExceededDragThreshold,
    applyWheelZoom,
  };
});
```

```python
with (dir_assets / "js" / "knowledge_graph_viewer.js").open(encoding="utf-8") as fi:
    self._kg_viewer_js = fi.read()
with (dir_assets / "js" / "main.js").open() as fi:
    self._js = self._kg_viewer_js + "\n" + fi.read()
```

- [ ] **Step 4: Re-run the Node tests and make sure they pass**

Run: `node --test libs/ktem/ktem/assets/js/knowledge_graph_viewer.test.js`

Expected: all tests `PASS`.

- [ ] **Step 5: Commit the viewer helper module**

```bash
git add libs/ktem/ktem/assets/js/knowledge_graph_viewer.js libs/ktem/ktem/assets/js/knowledge_graph_viewer.test.js libs/ktem/ktem/app.py
git commit -m "feat: add knowledge graph viewer math helpers"
```

## Task 4: Wire The Fullscreen Viewer, Preserve Node Clicks, And Add Overlay Styling

**Files:**

- Modify: `D:\PythonProject\kotaemon\libs\ktem\ktem\assets\js\main.js`
- Modify: `D:\PythonProject\kotaemon\libs\ktem\ktem\assets\css\main.css`
- Modify: `D:\PythonProject\kotaemon\libs\ktem\ktem_tests\test_knowledge_graph_service.py`

- [ ] **Step 1: Add one more failing renderer contract test for viewer controls**

```python
def test_render_graph_html_includes_viewer_toolbar_controls(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)
    graph = {
        "schema_version": 2,
        "source_ids": ["file-a"],
        "maps": [
            {
                "id": "map::1",
                "type": "knowledge_map",
                "kind": "map",
                "label": "Knowledge System 1",
                "summary": "Connected source set.",
                "related_file_ids": ["file-a"],
                "component_ids": [],
                "support_pages": {"file-a": ["1"]},
                "support_chunk_ids": {"file-a": ["chunk-a"]},
            }
        ],
        "components": [],
        "themes": [],
        "subthemes": [],
        "knowledge_points": [],
        "node_index": {},
        "support_pages": {"file-a": ["1"]},
        "support_chunk_ids": {"file-a": ["chunk-a"]},
    }

    rendered = service._render_graph_html(graph, focus_file_id="", status="ready")

    assert "data-kg-viewer-action='zoom-in'" in rendered
    assert "data-kg-viewer-action='zoom-out'" in rendered
    assert "data-kg-viewer-action='reset'" in rendered
    assert "data-kg-viewer-action='fit'" in rendered
    assert "data-kg-viewer-close='true'" in rendered
```

- [ ] **Step 2: Run the targeted pytest and confirm the toolbar test fails first**

Run: `.\.venv\Scripts\python.exe -m pytest libs\ktem\ktem_tests\test_knowledge_graph_service.py -k "viewer_toolbar_controls" -q`

Expected: `FAIL` until the toolbar control attributes are added.

- [ ] **Step 3: Implement the overlay lifecycle and pan/zoom wiring in `main.js`**

```javascript
function bindKnowledgeGraphViewer() {
  const graphPanel = document.querySelector("#knowledge-graph-plot");
  const shell = graphPanel?.querySelector(".knowledge-graph-shell");
  const overlay = shell?.querySelector("[data-kg-viewer-overlay='true']");
  const viewport = overlay?.querySelector("[data-kg-viewer-viewport='true']");
  const stage = overlay?.querySelector("[data-kg-viewer-stage='true']");
  const utils = globalThis.KnowledgeGraphViewerUtils;
  if (
    !shell ||
    !overlay ||
    !viewport ||
    !stage ||
    !utils ||
    shell.dataset.kgViewerBound === "true"
  ) {
    return;
  }

  shell.dataset.kgViewerBound = "true";
  let viewState = { scale: 1, translateX: 0, translateY: 0 };
  let pointerState = null;

  const applyStageTransform = () => {
    stage.style.transform = `translate(${viewState.translateX}px, ${viewState.translateY}px) scale(${viewState.scale})`;
  };

  const fitViewer = () => {
    const viewportRect = viewport.getBoundingClientRect();
    viewState = utils.computeFittedTransform({
      viewportWidth: viewportRect.width,
      viewportHeight: viewportRect.height,
      contentWidth: Math.max(stage.scrollWidth, stage.offsetWidth),
      contentHeight: Math.max(stage.scrollHeight, stage.offsetHeight),
      padding: 40,
      minScale: 0.35,
      maxScale: 2.5,
    });
    applyStageTransform();
  };

  shell.addEventListener("click", (event) => {
    const openTrigger = event.target.closest("[data-kg-open-viewer='true']");
    const closeTrigger = event.target.closest("[data-kg-viewer-close='true']");
    const actionTrigger = event.target.closest("[data-kg-viewer-action]");
    if (openTrigger) {
      overlay.hidden = false;
      document.body.classList.add("kg-viewer-open");
      fitViewer();
      return;
    }
    if (closeTrigger) {
      overlay.hidden = true;
      document.body.classList.remove("kg-viewer-open");
      return;
    }
    if (!actionTrigger) {
      return;
    }
    const action = actionTrigger.getAttribute("data-kg-viewer-action");
    if (action === "fit" || action === "reset") {
      fitViewer();
      return;
    }
    const midpoint = {
      cursorX: viewport.clientWidth / 2,
      cursorY: viewport.clientHeight / 2,
      minScale: 0.35,
      maxScale: 2.5,
      zoomStep: 0.14,
    };
    if (action === "zoom-in") {
      viewState = utils.applyWheelZoom(
        viewState,
        Object.assign({}, midpoint, { deltaY: -120 })
      );
      applyStageTransform();
      return;
    }
    if (action === "zoom-out") {
      viewState = utils.applyWheelZoom(
        viewState,
        Object.assign({}, midpoint, { deltaY: 120 })
      );
      applyStageTransform();
    }
  });

  viewport.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      const rect = viewport.getBoundingClientRect();
      viewState = utils.applyWheelZoom(viewState, {
        deltaY: event.deltaY,
        cursorX: event.clientX - rect.left,
        cursorY: event.clientY - rect.top,
        minScale: 0.35,
        maxScale: 2.5,
        zoomStep: 0.14,
      });
      applyStageTransform();
    },
    { passive: false }
  );

  viewport.addEventListener("pointerdown", (event) => {
    pointerState = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: viewState.translateX,
      originY: viewState.translateY,
      didDrag: false,
    };
    viewport.setPointerCapture(event.pointerId);
  });

  viewport.addEventListener("pointermove", (event) => {
    if (!pointerState || event.pointerId !== pointerState.pointerId) {
      return;
    }
    if (
      !pointerState.didDrag &&
      !utils.hasExceededDragThreshold(
        pointerState.startX,
        pointerState.startY,
        event.clientX,
        event.clientY,
        8
      )
    ) {
      return;
    }
    pointerState.didDrag = true;
    viewState.translateX =
      pointerState.originX + (event.clientX - pointerState.startX);
    viewState.translateY =
      pointerState.originY + (event.clientY - pointerState.startY);
    applyStageTransform();
  });

  viewport.addEventListener("pointerup", (event) => {
    if (!pointerState || event.pointerId !== pointerState.pointerId) {
      return;
    }
    viewport.releasePointerCapture(event.pointerId);
    pointerState = null;
  });
}

function bindKnowledgeGraphInteractions() {
  applyIconOnlyButtonTooltips();
  localizeUploadDropzoneText();
  cleanupKnowledgeGraphOverlayNodes();
  cleanupHtmlInfoPanelOverlay();
  bindKnowledgeGraphViewer();
  syncKnowledgeGraphFocus();
}
```

- [ ] **Step 4: Add the overlay, viewport, and preview-card styling in `main.css`**

```css
#knowledge-graph-plot .kg-preview-card {
  width: 100%;
  display: grid;
  gap: 10px;
  padding: 18px 20px;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--color-accent, #2563eb) 34%, #d4d4d8);
  background: radial-gradient(
      130% 180% at 0% 0%,
      rgba(109, 125, 255, 0.16),
      transparent 52%
    ), linear-gradient(140deg, rgba(18, 24, 44, 0.98), rgba(8, 12, 22, 0.96));
  text-align: left;
}

#knowledge-graph-plot .kg-viewer-overlay[hidden] {
  display: none !important;
}

#knowledge-graph-plot .kg-viewer-overlay {
  position: fixed;
  inset: 0;
  z-index: 1400;
  background: rgba(3, 6, 14, 0.78);
  padding: 24px;
}

#knowledge-graph-plot .kg-viewer-dialog {
  width: 100%;
  height: 100%;
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 12px;
  border-radius: 20px;
  border: 1px solid color-mix(in srgb, var(--color-accent, #2563eb) 30%, #334155);
  background: linear-gradient(
    140deg,
    rgba(10, 14, 24, 0.98),
    rgba(6, 9, 18, 0.98)
  );
  padding: 18px;
}

#knowledge-graph-plot .kg-viewer-viewport {
  position: relative;
  overflow: hidden;
  cursor: grab;
}

#knowledge-graph-plot .kg-viewer-stage {
  transform-origin: 0 0;
  will-change: transform;
}
```

- [ ] **Step 5: Run the focused verification suite for renderer, helper math, and script syntax**

Run: `.\.venv\Scripts\python.exe -m pytest libs\ktem\ktem_tests\test_knowledge_graph_service.py -q`

Expected: all knowledge-graph service tests `PASS`.

Run: `node --test libs/ktem/ktem/assets/js/knowledge_graph_viewer.test.js`

Expected: all helper tests `PASS`.

Run: `node --check libs/ktem/ktem/assets/js/main.js`

Expected: syntax check exits cleanly.

- [ ] **Step 6: Run the regression suite that protects event wiring and file-index refresh**

Run: `.\.venv\Scripts\python.exe -m pytest libs\ktem\ktem_tests\test_chat_knowledge_graph_bindings.py libs\ktem\ktem_tests\test_file_index_page_extraction.py -q`

Expected: existing chat knowledge-graph binding and file-index extraction tests stay green.

- [ ] **Step 7: Commit the fullscreen viewer implementation**

```bash
git add libs/ktem/ktem/assets/js/main.js libs/ktem/ktem/assets/css/main.css libs/ktem/ktem/pages/chat/knowledge_graph_renderer.py libs/ktem/ktem_tests/test_knowledge_graph_service.py
git commit -m "feat: add fullscreen knowledge graph viewer"
```

## Self-Review Checklist

- Spec coverage:
  - Preview card: Task 1 and Task 2
  - Fullscreen overlay: Task 1 and Task 4
  - Drag-to-pan and wheel zoom: Task 3 and Task 4
  - Toolbar controls: Task 4
  - Node click prompt filling preserved: Task 4
  - Split-map preview messaging: Task 2
  - Loading and empty card states: Task 2
- Placeholder scan:
  - The task steps do not contain unfinished placeholder instructions.
- Type consistency:
  - Preview trigger uses `data-kg-open-viewer`
  - Overlay uses `data-kg-viewer-overlay`
  - Viewport uses `data-kg-viewer-viewport`
  - Stage uses `data-kg-viewer-stage`
  - Toolbar uses `data-kg-viewer-action`

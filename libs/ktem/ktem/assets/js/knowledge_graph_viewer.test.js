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

test("computeModeratedAnchorTranslation ignores tiny anchor drift", () => {
  const result = viewer.computeModeratedAnchorTranslation(
    { left: 120, top: 80 },
    { left: 123, top: 82 },
    { threshold: 4, maxShift: 120 }
  );

  assert.deepEqual(result, { translateX: 0, translateY: 0 });
});

test("computeModeratedAnchorTranslation clamps large anchor drift", () => {
  const result = viewer.computeModeratedAnchorTranslation(
    { left: 460, top: 280 },
    { left: 180, top: 120 },
    { threshold: 4, maxShift: 90 }
  );

  assert.equal(result.translateX, 90);
  assert.equal(result.translateY, 90);
});

test("shouldIgnorePanTarget treats interactive graph controls as non-draggable", () => {
  const fakeTarget = {
    closest(selector) {
      return selector.includes("[data-kg-branch-toggle='true']") ? {} : null;
    },
  };

  assert.equal(viewer.shouldIgnorePanTarget(fakeTarget), true);
});

test("shouldIgnorePanTarget allows passive canvas targets", () => {
  const fakeTarget = {
    closest() {
      return null;
    },
  };

  assert.equal(viewer.shouldIgnorePanTarget(fakeTarget), false);
});

test("buildConnectorPath returns a rounded branch path between the spine and node", () => {
  const path = viewer.buildConnectorPath({
    startX: 0,
    startY: 24,
    endX: 84,
    endY: 60,
  });

  assert.equal(path, "M 0 24 L 15 24 Q 21 24 21 30 L 21 54 Q 21 60 27 60 L 84 60");
});

test("buildConnectorTrunkPath creates a shared vertical spine for sibling branches", () => {
  const path = viewer.buildConnectorTrunkPath({
    startX: 0,
    startY: 48,
    trunkX: 18,
    topY: 18,
    bottomY: 92,
  });

  assert.equal(path, "M 0 48 L 12 48 Q 18 48 18 42 L 18 24 Q 18 18 18 18 M 18 54 L 18 86 Q 18 92 18 92");
});

test("getConnectorRefreshDelays includes a post-transition render pass", () => {
  assert.deepEqual(viewer.getConnectorRefreshDelays({ transitionMs: 320 }), [
    0,
    160,
    360,
  ]);
});

test("shouldRefreshConnectorForTransition filters to branch animation properties", () => {
  assert.equal(viewer.shouldRefreshConnectorForTransition("width"), true);
  assert.equal(viewer.shouldRefreshConnectorForTransition("height"), true);
  assert.equal(viewer.shouldRefreshConnectorForTransition("transform"), true);
  assert.equal(viewer.shouldRefreshConnectorForTransition("margin-left"), true);
  assert.equal(viewer.shouldRefreshConnectorForTransition("opacity"), true);
  assert.equal(viewer.shouldRefreshConnectorForTransition("background-color"), false);
});

test("measureOffsetBoxWithin uses local layout coordinates instead of scaled viewport rects", () => {
  const branch = {
    offsetLeft: 0,
    offsetTop: 0,
    offsetWidth: 320,
    offsetHeight: 180,
    offsetParent: null,
  };
  const childrenViewport = {
    offsetLeft: 96,
    offsetTop: 8,
    offsetWidth: 180,
    offsetHeight: 120,
    offsetParent: branch,
    getBoundingClientRect() {
      return { left: 140, top: 40, width: 270, height: 180 };
    },
  };
  const toggleAnchor = {
    offsetLeft: 52,
    offsetTop: 18,
    offsetWidth: 34,
    offsetHeight: 34,
    offsetParent: branch,
    getBoundingClientRect() {
      return { left: 80, top: 55, width: 51, height: 51 };
    },
  };

  const viewportBox = viewer.measureOffsetBoxWithin(childrenViewport, branch);
  const toggleBox = viewer.measureOffsetBoxWithin(toggleAnchor, branch);

  assert.deepEqual(viewportBox, {
    left: 96,
    top: 8,
    width: 180,
    height: 120,
  });
  assert.deepEqual(toggleBox, {
    left: 52,
    top: 18,
    width: 34,
    height: 34,
  });
});

test("computeConnectorStartY falls back to the branch self anchor when toggle is missing", () => {
  const startY = viewer.computeConnectorStartY({
    viewportBox: { top: 80 },
    selfBox: { top: 32, height: 40 },
  });

  assert.equal(startY, -28);
});

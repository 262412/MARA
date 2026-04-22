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

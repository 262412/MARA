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
    const viewportWidth = Math.max(1, Number(options.viewportWidth) || 1);
    const viewportHeight = Math.max(1, Number(options.viewportHeight) || 1);
    const contentWidth = Math.max(1, Number(options.contentWidth) || 1);
    const contentHeight = Math.max(1, Number(options.contentHeight) || 1);
    const padding = Math.max(0, Number(options.padding) || 0);
    const minScale = Number(options.minScale) || 0.35;
    const maxScale = Number(options.maxScale) || 2.5;
    const availableWidth = Math.max(1, viewportWidth - padding * 2);
    const availableHeight = Math.max(1, viewportHeight - padding * 2);
    const fitScale = clampGraphScale(
      Math.min(availableWidth / contentWidth, availableHeight / contentHeight),
      minScale,
      maxScale
    );

    return {
      scale: fitScale,
      translateX: (viewportWidth - contentWidth * fitScale) / 2,
      translateY: (viewportHeight - contentHeight * fitScale) / 2,
    };
  }

  function hasExceededDragThreshold(startX, startY, currentX, currentY, threshold) {
    const deltaX = Math.abs((Number(currentX) || 0) - (Number(startX) || 0));
    const deltaY = Math.abs((Number(currentY) || 0) - (Number(startY) || 0));
    const limit = Math.max(0, Number(threshold) || 0);
    return deltaX >= limit || deltaY >= limit;
  }

  function applyWheelZoom(state, options) {
    const scale = Math.max(0.0001, Number(state.scale) || 1);
    const translateX = Number(state.translateX) || 0;
    const translateY = Number(state.translateY) || 0;
    const deltaY = Number(options.deltaY) || 0;
    const cursorX = Number(options.cursorX) || 0;
    const cursorY = Number(options.cursorY) || 0;
    const minScale = Number(options.minScale) || 0.35;
    const maxScale = Number(options.maxScale) || 2.5;
    const zoomStep = Math.max(0.001, Number(options.zoomStep) || 0.14);
    const direction = deltaY < 0 ? 1 : -1;
    const nextScale = clampGraphScale(
      scale * (1 + direction * zoomStep),
      minScale,
      maxScale
    );
    const ratio = nextScale / scale;

    return {
      scale: nextScale,
      translateX: cursorX - (cursorX - translateX) * ratio,
      translateY: cursorY - (cursorY - translateY) * ratio,
    };
  }

  return {
    clampGraphScale,
    computeFittedTransform,
    hasExceededDragThreshold,
    applyWheelZoom,
  };
});

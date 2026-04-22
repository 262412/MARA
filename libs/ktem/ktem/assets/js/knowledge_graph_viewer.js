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

  function computeModeratedAnchorTranslation(beforeRect, afterRect, options) {
    const threshold = Math.max(0, Number(options?.threshold) || 0);
    const maxShift = Math.max(threshold, Number(options?.maxShift) || 0);
    const beforeLeft = Number(beforeRect?.left) || 0;
    const beforeTop = Number(beforeRect?.top) || 0;
    const afterLeft = Number(afterRect?.left) || 0;
    const afterTop = Number(afterRect?.top) || 0;

    const clampDelta = (value) => {
      const magnitude = Math.abs(Number(value) || 0);
      if (magnitude <= threshold) {
        return 0;
      }
      return Math.sign(value) * Math.min(magnitude, maxShift);
    };

    return {
      translateX: clampDelta(beforeLeft - afterLeft),
      translateY: clampDelta(beforeTop - afterTop),
    };
  }

  function shouldIgnorePanTarget(target) {
    if (!target || typeof target.closest !== "function") {
      return false;
    }
    return Boolean(
      target.closest(
        [
          "button",
          "a",
          "input",
          "textarea",
          "select",
          "label",
          "summary",
          "[data-kg-payload]",
          "[data-kg-branch-toggle='true']",
          "[data-kg-viewer-action]",
          "[data-kg-viewer-close='true']",
          "[data-kg-open-viewer='true']",
        ].join(",")
      )
    );
  }

  function clampConnectorRadius(value) {
    return Math.max(0, Number(value) || 0);
  }

  function getConnectorRefreshDelays(options) {
    const transitionMs = Math.max(0, Number(options?.transitionMs) || 0);
    const midpoint = Math.max(0, Math.round(transitionMs / 2));
    const afterTransition = Math.max(0, transitionMs + 40);
    return [0, midpoint, afterTransition];
  }

  function shouldRefreshConnectorForTransition(propertyName) {
    const property = String(propertyName || "").trim().toLowerCase();
    return [
      "width",
      "height",
      "margin-left",
      "transform",
      "opacity",
      "filter",
    ].includes(property);
  }

  function buildConnectorPath(options) {
    const startX = Number(options?.startX) || 0;
    const startY = Number(options?.startY) || 0;
    const endX = Number(options?.endX) || 0;
    const endY = Number(options?.endY) || 0;
    const deltaX = Math.max(0, endX - startX);
    const deltaY = endY - startY;

    if (deltaX <= 0) {
      return `M ${startX} ${startY} L ${endX} ${endY}`;
    }

    if (Math.abs(deltaY) <= 0.5) {
      return `M ${startX} ${startY} L ${endX} ${endY}`;
    }

    const trunkX = Number(
      (
        startX +
        Math.max(16, Math.min(24, deltaX * 0.25))
      ).toFixed(1)
    );
    const directionY = deltaY > 0 ? 1 : -1;
    const radius = Number(
      clampConnectorRadius(
        Math.min(6, Math.abs(deltaY) / 2, Math.max(4, deltaX * 0.12))
      ).toFixed(1)
    );
    const leadX = Number((trunkX - radius).toFixed(1));
    const bendY = Number((startY + radius * directionY).toFixed(1));
    const verticalEndY = Number((endY - radius * directionY).toFixed(1));
    const exitX = Number((trunkX + radius).toFixed(1));

    return [
      `M ${startX} ${startY}`,
      `L ${leadX} ${startY}`,
      `Q ${trunkX} ${startY} ${trunkX} ${bendY}`,
      `L ${trunkX} ${verticalEndY}`,
      `Q ${trunkX} ${endY} ${exitX} ${endY}`,
      `L ${endX} ${endY}`,
    ].join(" ");
  }

  function buildConnectorTrunkPath(options) {
    const startX = Number(options?.startX) || 0;
    const startY = Number(options?.startY) || 0;
    const trunkX = Number(options?.trunkX) || 0;
    const topY = Number(options?.topY) || 0;
    const bottomY = Number(options?.bottomY) || 0;
    const radius = Number(
      clampConnectorRadius(
        Math.min(
          6,
          Math.abs(startY - topY),
          Math.abs(bottomY - startY),
          Math.max(4, Math.abs(trunkX - startX) * 0.35)
        )
      ).toFixed(1)
    );
    const leadX = Number((trunkX - radius).toFixed(1));
    const upperStartY = Number((startY - radius).toFixed(1));
    const upperVerticalEndY = Number((topY + radius).toFixed(1));
    const lowerStartY = Number((startY + radius).toFixed(1));
    const lowerVerticalEndY = Number((bottomY - radius).toFixed(1));

    return [
      `M ${startX} ${startY}`,
      `L ${leadX} ${startY}`,
      `Q ${trunkX} ${startY} ${trunkX} ${upperStartY}`,
      `L ${trunkX} ${upperVerticalEndY}`,
      `Q ${trunkX} ${topY} ${trunkX} ${topY}`,
      `M ${trunkX} ${lowerStartY}`,
      `L ${trunkX} ${lowerVerticalEndY}`,
      `Q ${trunkX} ${bottomY} ${trunkX} ${bottomY}`,
    ].join(" ");
  }

  function measureOffsetBoxWithin(target, root) {
    if (!target || !root) {
      return null;
    }

    let left = 0;
    let top = 0;
    let node = target;

    while (node && node !== root) {
      left += Number(node.offsetLeft) || 0;
      top += Number(node.offsetTop) || 0;
      node = node.offsetParent || null;
    }

    if (node !== root) {
      return null;
    }

    return {
      left,
      top,
      width: Math.max(Number(target.offsetWidth) || Number(target.clientWidth) || 0, 0),
      height: Math.max(
        Number(target.offsetHeight) || Number(target.clientHeight) || 0,
        0
      ),
    };
  }

  function computeConnectorStartY(options) {
    const viewportTop = Number(options?.viewportBox?.top) || 0;
    const anchorBox = options?.toggleBox || options?.selfBox || null;
    if (!anchorBox) {
      return Number(options?.fallbackY) || 24;
    }
    return (
      (Number(anchorBox.top) || 0) +
      (Number(anchorBox.height) || 0) / 2 -
      viewportTop
    );
  }

  return {
    clampGraphScale,
    computeFittedTransform,
    hasExceededDragThreshold,
    applyWheelZoom,
    computeModeratedAnchorTranslation,
    shouldIgnorePanTarget,
    buildConnectorPath,
    buildConnectorTrunkPath,
    getConnectorRefreshDelays,
    shouldRefreshConnectorForTransition,
    measureOffsetBoxWithin,
    computeConnectorStartY,
  };
});

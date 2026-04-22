function run() {
  let answerPanelObserver = globalThis._ktemAnswerPanelObserver || null;
  let previewSrcPoller = globalThis._ktemPreviewSrcPoller || null;
  let knowledgeGraphObserver = globalThis._ktemKnowledgeGraphObserver || null;
  let lastPreviewSrc = globalThis._ktemLastPreviewSrc || null;
  let selectionPromptBox = null;
  let selectionPromptInput = null;
  let selectionPromptAsk = null;
  let selectionPromptClose = null;
  let currentSelectedPageText = "";
  let officeZoomControl = null;
  let officeZoomSlider = null;
  let officeZoomLabel = null;
  let isOfficePreview = false;
  let lastNonEmptySelectionTs = 0;
  let lastAssignedPreviewSrc = globalThis._ktemLastAssignedPreviewSrc || "";
  let lastStablePreviewSrc = globalThis._ktemLastStablePreviewSrc || "";
  let lastPostedPageDocKey = globalThis._ktemLastPostedPageDocKey || "";
  let lastPostedPageNumber = globalThis._ktemLastPostedPageNumber || 0;
  let lastNonEmptyPreviewSrcTs = globalThis._ktemLastNonEmptyPreviewSrcTs || 0;

  function parsePreviewFitMode(src) {
    try {
      let url = new URL(src, window.location.origin);
      return (url.searchParams.get("ktemfit") || "pdf").toLowerCase();
    } catch (error) {
      return "pdf";
    }
  }

  function findLastActiveField(selector) {
    const fields = document.querySelectorAll(selector);
    if (!fields || fields.length === 0) {
      return null;
    }
    for (let i = fields.length - 1; i >= 0; i--) {
      const candidate = fields[i];
      const value = (candidate && candidate.value ? candidate.value : "").trim();
      if (value) {
        return candidate;
      }
    }
    return fields[fields.length - 1] || null;
  }

  function getPageFromPreviewSrc(src) {
    try {
      const u = new URL(src, window.location.origin);
      const queryPage = parseInt(u.searchParams.get("ktempage") || "", 10);
      if (Number.isFinite(queryPage) && queryPage > 0) return queryPage;
      const hashParams = new URLSearchParams((u.hash || "").replace(/^#/, ""));
      const hashPage = parseInt(hashParams.get("page") || "", 10);
      return Number.isFinite(hashPage) && hashPage > 0 ? hashPage : null;
    } catch (error) {
      return null;
    }
  }

  function withPreviewPageHash(src, page) {
    try {
      const u = new URL(src, window.location.origin);
      if (Number.isFinite(page) && page > 0) {
        u.searchParams.set("ktempage", String(page));
        u.hash = `page=${page}`;
      }
      return u.toString();
    } catch (error) {
      return src;
    }
  }

  function toAbsolutePreviewSrc(src) {
    try {
      return new URL(src, window.location.origin).toString();
    } catch (error) {
      return src || "";
    }
  }

  function getPreviewDocKey(src) {
    try {
      const u = new URL(src, window.location.origin);
      const fileParam = u.searchParams.get("file") || "";
      return `${u.pathname}|${fileParam}`;
    } catch (error) {
      return (src || "").split("#")[0];
    }
  }

  function updateLastPostedPageSync(docKey, page) {
    lastPostedPageDocKey = docKey || "";
    lastPostedPageNumber = page;
    globalThis._ktemLastPostedPageDocKey = lastPostedPageDocKey;
    globalThis._ktemLastPostedPageNumber = lastPostedPageNumber;
  }

  function postPageChangeIfNeeded(targetIframe, targetPage, docKey, force = false) {
    if (
      !targetIframe ||
      !targetIframe.contentWindow ||
      !Number.isFinite(targetPage) ||
      targetPage <= 0
    ) {
      return false;
    }
    const normalizedDocKey = docKey || "";
    if (
      !force &&
      normalizedDocKey &&
      normalizedDocKey === lastPostedPageDocKey &&
      targetPage === lastPostedPageNumber
    ) {
      return false;
    }
    try {
      targetIframe.contentWindow.postMessage(
        { type: "ktem-pdf-page-change", page: targetPage },
        window.location.origin
      );
      updateLastPostedPageSync(normalizedDocKey, targetPage);
      return true;
    } catch (error) {
      return false;
    }
  }

  function updateLastAssignedPreviewSrc(src) {
    lastAssignedPreviewSrc = src || "";
    globalThis._ktemLastAssignedPreviewSrc = lastAssignedPreviewSrc;
  }

  function updateLastStablePreviewSrc(src) {
    lastStablePreviewSrc = src || "";
    globalThis._ktemLastStablePreviewSrc = lastStablePreviewSrc;
    if (lastStablePreviewSrc) {
      lastNonEmptyPreviewSrcTs = Date.now();
      globalThis._ktemLastNonEmptyPreviewSrcTs = lastNonEmptyPreviewSrcTs;
    }
  }

  function clearPreviewSyncState() {
    lastPreviewSrc = null;
    globalThis._ktemLastPreviewSrc = lastPreviewSrc;
    updateLastAssignedPreviewSrc("");
    updateLastStablePreviewSrc("");
    updateLastPostedPageSync("", 0);
  }

  function isLikelyPreviewSrc(src) {
    if (!src || typeof src !== "string") {
      return false;
    }
    const trimmed = src.trim();
    if (!trimmed) {
      return false;
    }
    if (isDataHtmlPreviewSrc(trimmed)) {
      return true;
    }
    if (isInlineHtmlPreviewSrc(trimmed)) {
      return true;
    }
    if (
      trimmed.startsWith("data:image") ||
      /\.(png|jpg|jpeg|gif|webp|svg)(\?|#|$)/i.test(trimmed)
    ) {
      return true;
    }
    if (trimmed.includes("/file=")) {
      return true;
    }
    try {
      const url = new URL(trimmed, window.location.origin);
      return (url.pathname || "").includes("/file=");
    } catch (error) {
      return false;
    }
  }

  function isDataHtmlPreviewSrc(src) {
    if (!src || typeof src !== "string") {
      return false;
    }
    return /^data:text\/html/i.test(src.trim());
  }

  function isInlineHtmlPreviewSrc(src) {
    if (!src || typeof src !== "string") {
      return false;
    }
    const trimmed = src.trim();
    if (!trimmed) {
      return false;
    }
    return trimmed.startsWith("<");
  }

  function dataHtmlToSrcdoc(dataUri) {
    try {
      const value = (dataUri || "").trim();
      if (!/^data:text\/html/i.test(value)) {
        return "";
      }
      const commaPos = value.indexOf(",");
      if (commaPos < 0) {
        return "";
      }
      const meta = value.slice(0, commaPos).toLowerCase();
      const body = value.slice(commaPos + 1);
      if (meta.includes(";base64")) {
        return atob(body);
      }
      return decodeURIComponent(body);
    } catch (error) {
      return "";
    }
  }

  function ensureOfficeZoomControl() {
    if (officeZoomControl) {
      return;
    }
    const shell = document.querySelector("#main-pdf-preview .pdf-preview-shell");
    if (!shell) {
      return;
    }

    officeZoomControl = document.createElement("div");
    officeZoomControl.id = "ktem-office-zoom-control";
    officeZoomControl.style.position = "absolute";
    officeZoomControl.style.right = "10px";
    officeZoomControl.style.bottom = "10px";
    officeZoomControl.style.zIndex = "10";
    officeZoomControl.style.display = "none";
    officeZoomControl.style.alignItems = "center";
    officeZoomControl.style.gap = "8px";
    officeZoomControl.style.padding = "6px 8px";
    officeZoomControl.style.borderRadius = "10px";
    officeZoomControl.style.background = "rgba(255,255,255,0.95)";
    officeZoomControl.style.border = "1px solid var(--border-color-primary,#d4d4d8)";
    officeZoomControl.style.boxShadow = "0 4px 12px rgba(0,0,0,0.1)";
    officeZoomControl.innerHTML = `
      <span style="font-size:12px;color:#111827;white-space:nowrap;">Zoom</span>
      <input id="ktem-office-zoom-slider" type="range" min="35" max="250" step="5" value="100" style="width:140px;accent-color:#2563eb;" />
      <span id="ktem-office-zoom-label" style="font-size:12px;min-width:42px;text-align:right;color:#111827;">100%</span>
    `;
    shell.appendChild(officeZoomControl);

    officeZoomSlider = officeZoomControl.querySelector("#ktem-office-zoom-slider");
    officeZoomLabel = officeZoomControl.querySelector("#ktem-office-zoom-label");
    if (officeZoomSlider) {
      officeZoomSlider.addEventListener("input", () => {
        const iframe = document.getElementById("main-pdf-preview-frame");
        if (!iframe || !iframe.contentWindow || !isOfficePreview) {
          return;
        }
        const zoomValue = parseInt(officeZoomSlider.value || "100", 10);
        if (officeZoomLabel) {
          officeZoomLabel.textContent = `${zoomValue}%`;
        }
        iframe.contentWindow.postMessage(
          { type: "ktem-pdf-zoom-set", zoom: zoomValue / 100 },
          window.location.origin
        );
      });
    }
  }

  function setOfficeZoomControlVisible(visible) {
    ensureOfficeZoomControl();
    if (!officeZoomControl) {
      return;
    }
    officeZoomControl.style.display = visible ? "inline-flex" : "none";
  }

  function updateOfficeZoomControl(scaleValue) {
    if (!officeZoomSlider || !officeZoomLabel) {
      return;
    }
    const percent = Math.max(35, Math.min(250, Math.round((scaleValue || 1) * 100)));
    officeZoomSlider.value = String(percent);
    officeZoomLabel.textContent = `${percent}%`;
  }

  function enforceAnswerPanelScroll() {
    let answerPanel = document.getElementById("answer-panel");
    let answerExpand = document.getElementById("answer-expand");
    if (!answerPanel || !answerExpand) {
      return;
    }

    answerExpand.style.overflow = "hidden";
    answerExpand.style.minHeight = "0";

    let node = answerPanel.parentElement;
    while (node && node !== answerExpand) {
      node.style.minHeight = "0";
      node.style.height = "100%";
      node.style.maxHeight = "100%";
      node.style.overflow = "hidden";
      node = node.parentElement;
    }

    answerPanel.style.minHeight = "0";
    answerPanel.style.height = "100%";
    answerPanel.style.maxHeight = "100%";
    answerPanel.style.overflowX = "hidden";
    answerPanel.style.overflowY = "auto";
  }

  function syncMainPdfPreview() {
    const currentPage = getCurrentPageNumber();
    const srcField = findLastActiveField(
      "#main-pdf-preview-src textarea, #main-pdf-preview-src input"
    );
    let iframe = document.getElementById("main-pdf-preview-frame");
    let image = document.getElementById("main-pdf-preview-image");
    let empty = document.getElementById("main-pdf-preview-empty");
    if (!srcField || !iframe || !image || !empty) {
      return;
    }

    let nextSrc = (srcField?.value || "").trim();
    const currentIframeSrc = (iframe.getAttribute("src") || "").trim();
    if (!nextSrc) {
      // Gradio can transiently clear hidden field values during rerenders.
      // Keep rendering the last stable preview source instead of blanking UI.
      const now = Date.now();
      const withinGraceWindow =
        lastNonEmptyPreviewSrcTs > 0 && now - lastNonEmptyPreviewSrcTs < 1200;
      if (withinGraceWindow && lastStablePreviewSrc) {
        nextSrc = lastStablePreviewSrc;
      } else if (withinGraceWindow && currentIframeSrc) {
        nextSrc = currentIframeSrc;
      } else {
        isOfficePreview = false;
        setOfficeZoomControlVisible(false);
        iframe.style.display = "none";
        image.style.display = "none";
        empty.style.display = "flex";
        iframe.removeAttribute("src");
        iframe.removeAttribute("srcdoc");
        image.removeAttribute("src");
        clearPreviewSyncState();
        return;
      }
    }

    const inlineHtmlPreview = isInlineHtmlPreviewSrc(nextSrc);
    const dataHtmlPreview = isDataHtmlPreviewSrc(nextSrc);
    const passthroughPreview = inlineHtmlPreview || dataHtmlPreview;
    const nextDocKey = passthroughPreview ? "" : getPreviewDocKey(nextSrc);
    const currentDocKey = passthroughPreview ? "" : getPreviewDocKey(currentIframeSrc);
    const chosenPage = getPageFromPreviewSrc(nextSrc);
    const desiredPage = Number.isFinite(currentPage) && currentPage > 0 ? currentPage : chosenPage;
    const normalizedNextSrc = passthroughPreview
      ? nextSrc
      : toAbsolutePreviewSrc(withPreviewPageHash(nextSrc, desiredPage));
    const normalizedCurrentSrc = inlineHtmlPreview
      ? (iframe.srcdoc || "")
      : (passthroughPreview ? currentIframeSrc : toAbsolutePreviewSrc(currentIframeSrc));
    const sameDoc =
      !!nextDocKey &&
      !!currentDocKey &&
      nextDocKey === currentDocKey;

    if (!passthroughPreview && iframe.hasAttribute("srcdoc")) {
      // Ensure PDF/image navigation is not shadowed by a leftover srcdoc.
      iframe.removeAttribute("srcdoc");
    }

    if (
      (nextSrc === lastPreviewSrc || normalizedNextSrc === lastAssignedPreviewSrc) &&
      normalizedCurrentSrc === normalizedNextSrc
    ) {
      return;
    }
    lastPreviewSrc = nextSrc;
    globalThis._ktemLastPreviewSrc = nextSrc;

    if (!isLikelyPreviewSrc(nextSrc)) {
      isOfficePreview = false;
      setOfficeZoomControlVisible(false);
      iframe.style.display = "none";
      image.style.display = "none";
      empty.style.display = "flex";
      iframe.removeAttribute("src");
      iframe.removeAttribute("srcdoc");
      image.removeAttribute("src");
      clearPreviewSyncState();
      return;
    }

    const isImage = nextSrc.startsWith("data:image") || /\.(png|jpg|jpeg|gif|webp|svg)(\?|#|$)/i.test(nextSrc);
    if (isImage) {
      isOfficePreview = false;
      setOfficeZoomControlVisible(false);
      iframe.removeAttribute("srcdoc");
      iframe.style.display = "none";
      empty.style.display = "none";
      image.style.display = "block";
      image.src = nextSrc;
      return;
    }

    if (inlineHtmlPreview || dataHtmlPreview) {
      isOfficePreview = false;
      setOfficeZoomControlVisible(false);
      image.style.display = "none";
      empty.style.display = "none";
      iframe.style.display = "block";
      iframe.style.width = "100%";
      iframe.style.height = "100%";
      iframe.onload = () => {
        bindIframeSelectionFallback(iframe);
      };
      const htmlSrcdoc = inlineHtmlPreview ? nextSrc : dataHtmlToSrcdoc(nextSrc);
      if (htmlSrcdoc) {
        if (iframe.srcdoc !== htmlSrcdoc) {
          iframe.srcdoc = htmlSrcdoc;
        }
        iframe.removeAttribute("src");
      } else {
        const fallbackSrc = dataHtmlPreview ? nextSrc : "about:blank";
        iframe.removeAttribute("srcdoc");
        iframe.setAttribute("src", fallbackSrc);
      }
      bindIframeSelectionFallback(iframe);
      updateLastPostedPageSync("", 0);
      updateLastAssignedPreviewSrc(nextSrc);
      updateLastStablePreviewSrc(nextSrc);
      return;
    }

    image.style.display = "none";
    empty.style.display = "none";
    iframe.style.display = "block";
    iframe.removeAttribute("srcdoc");
    const fitMode = parsePreviewFitMode(nextSrc);
    isOfficePreview = fitMode === "office";
    setOfficeZoomControlVisible(isOfficePreview);

    iframe.onload = () => {
      bindIframeSelectionFallback(iframe);
      if (!iframe.contentWindow) {
        return;
      }
      postPageChangeIfNeeded(iframe, desiredPage, nextDocKey, true);
      if (isOfficePreview) {
        iframe.contentWindow.postMessage(
          { type: "ktem-pdf-zoom-request" },
          window.location.origin
        );
      }
    };
    iframe.style.display = "block";
    iframe.style.width = "100%";
    iframe.style.height = "100%";

    // Avoid iframe reload flicker when switching pages within the same document.
    if (sameDoc && iframe.contentWindow) {
      postPageChangeIfNeeded(iframe, desiredPage, nextDocKey, false);
      if (normalizedNextSrc) {
        updateLastAssignedPreviewSrc(normalizedNextSrc);
        updateLastStablePreviewSrc(normalizedNextSrc);
      }
      return;
    }

    nextSrc = normalizedNextSrc;
    if (normalizedCurrentSrc === normalizedNextSrc) {
      if (normalizedNextSrc) {
        updateLastStablePreviewSrc(normalizedNextSrc);
      }
      return;
    }
    updateLastPostedPageSync("", 0);
    iframe.src = nextSrc;
    updateLastAssignedPreviewSrc(nextSrc);
    if (nextSrc) {
      updateLastStablePreviewSrc(nextSrc);
    }
  }

  function bindIframeSelectionFallback(iframe) {
    if (!iframe || iframe._ktemSelectionFallbackBound) {
      return;
    }
    iframe._ktemSelectionFallbackBound = true;

    const attach = () => {
      try {
        const doc = iframe.contentDocument || iframe.contentWindow?.document;
        if (!doc || doc._ktemSelectionFallbackAttached) {
          return;
        }
        doc._ktemSelectionFallbackAttached = true;
        doc.addEventListener("mouseup", () => {
          try {
            const sel = iframe.contentWindow?.getSelection?.();
            const text = (sel && sel.toString ? sel.toString() : "").trim();
            if (!text) {
              if (Date.now() - lastNonEmptySelectionTs >= 200) {
                hideSelectionPrompt();
              }
              return;
            }
            let rect = { left: 0, top: 0, width: 0, height: 0 };
            const range = sel.rangeCount > 0 ? sel.getRangeAt(0) : null;
            if (range) {
              const r = range.getBoundingClientRect();
              rect = {
                left: Number.isFinite(r.left) ? r.left : 0,
                top: Number.isFinite(r.top) ? r.top : 0,
                width: Number.isFinite(r.width) ? r.width : 0,
                height: Number.isFinite(r.height) ? r.height : 0,
              };
            }
            currentSelectedPageText = text.slice(0, 2000);
            setSelectedPageText(currentSelectedPageText);
            lastNonEmptySelectionTs = Date.now();
            showSelectionPromptNearRect(rect);
          } catch (error) {
            // ignore fallback selection errors
          }
        });
      } catch (error) {
        // ignore iframe access errors
      }
    };

    iframe.addEventListener("load", attach);
    attach();
  }

  function setSelectedPageText(value) {
    let selectionField = document.querySelector(
      "#selected-page-text textarea, #selected-page-text input"
    );
    if (!selectionField) {
      return;
    }

    selectionField.value = value || "";
    selectionField.dispatchEvent(new Event("input", { bubbles: true }));
    selectionField.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function getSelectedPageTextValue() {
    const field = document.querySelector(
      "#selected-page-text textarea, #selected-page-text input"
    );
    const stateValue = (currentSelectedPageText || "").trim();
    const fieldValue = (field?.value || "").trim();
    return stateValue || fieldValue;
  }

  function setKnowledgeGraphContext(value) {
    let graphContextField = document.querySelector(
      "#selected-graph-context textarea, #selected-graph-context input"
    );
    if (!graphContextField) {
      return;
    }

    graphContextField.value = value || "";
    graphContextField.dispatchEvent(new Event("input", { bubbles: true }));
    graphContextField.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fillChatInputWithoutSubmit(question) {
    const chatInput = getChatInputField();
    if (!chatInput || !question) {
      return;
    }
    chatInput.value = question;
    chatInput.dispatchEvent(new Event("input", { bubbles: true }));
    chatInput.dispatchEvent(new Event("change", { bubbles: true }));
    chatInput.focus();
  }

  function renderKnowledgeGraphAnswerHint(payload) {
    const hintContainer = document.querySelector("#kg-answer-hint");
    if (!hintContainer) {
      return;
    }

    if (!payload || typeof payload !== "object") {
      hintContainer.innerHTML =
        "<div class='kg-answer-hint kg-answer-hint--empty'>Select a node in the knowledge graph mind map to pin context and load a draft question.</div>";
      return;
    }

    const graphContext = payload.graph_context || {};
    const label = String(payload.node_label || graphContext.label || "Selected node").trim();
    const summary = String(payload.summary || "").trim();
    const suggestedQuestion = String(
      payload.fill_question || payload.suggested_question || payload.prompt || ""
    ).trim();
    const rawNodeType = String(
      payload.node_role || payload.node_type || graphContext.node_role || graphContext.type || ""
    ).trim();
    const nodeTypeMap = {
      knowledge_root: "Root",
      knowledge_map: "Knowledge Map",
      component: "Component",
      knowledge_system: "Component",
      theme: "Theme",
      system_relation: "Theme",
      subtheme: "Subtheme",
      file_summary: "Subtheme",
      knowledge_point: "Knowledge Point",
    };
    const nodeStyleClassMap = {
      knowledge_root: "kg-tree-node--root",
      knowledge_map: "kg-tree-node--root",
      component: "kg-tree-node--component",
      knowledge_system: "kg-tree-node--component",
      theme: "kg-tree-node--theme",
      system_relation: "kg-tree-node--theme",
      subtheme: "kg-tree-node--subtheme",
      file_summary: "kg-tree-node--subtheme",
      knowledge_point: "kg-tree-node--point",
    };
    const nodeType = nodeTypeMap[rawNodeType] || (rawNodeType || "Node");
    const nodeStyleClass =
      nodeStyleClassMap[rawNodeType] || "kg-tree-node--point";

    hintContainer.innerHTML = `
      <div class="kg-answer-hint">
        <div class="kg-answer-hint__title">Knowledge Graph Context</div>
        <div class="kg-answer-hint__node ${nodeStyleClass}">
          <span class="kg-answer-hint__label">${escapeHtml(label)}</span>
          <span class="kg-answer-hint__type">${escapeHtml(nodeType)}</span>
        </div>
        ${summary ? `<p class="kg-answer-hint__summary">${escapeHtml(summary)}</p>` : ""}
        ${
          suggestedQuestion
            ? `<div class="kg-answer-hint__actions"><button type="button" class="kg-answer-hint__ask ${nodeStyleClass}" data-kg-fill-question="${escapeHtml(
                suggestedQuestion
              )}">Load into chat</button></div>`
            : ""
        }
      </div>
    `;
  }

  function setChatFileClick(value) {
    let fileClickField = document.querySelector(
      "#chat-file-click textarea, #chat-file-click input"
    );
    if (!fileClickField) {
      return;
    }

    fileClickField.value = value || "";
    fileClickField.dispatchEvent(new Event("input", { bubbles: true }));
    fileClickField.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function getChatInputField() {
    return document.querySelector("#chat-input textarea");
  }

  function submitChatInput() {
    const chatInput = getChatInputField();
    if (!chatInput) {
      return;
    }

    const candidates = Array.from(
      document.querySelectorAll("#chat-input-row button")
    ).filter((btn) => {
      if (!btn || btn.disabled) return false;
      const style = window.getComputedStyle(btn);
      if (style.display === "none" || style.visibility === "hidden") return false;
      return true;
    });

    const semanticButton = candidates.find((btn) => {
      const text = (btn.innerText || "").toLowerCase();
      const aria = (btn.getAttribute("aria-label") || "").toLowerCase();
      const title = (btn.getAttribute("title") || "").toLowerCase();
      const cls = (btn.className || "").toLowerCase();
      return (
        text.includes("send") ||
        text.includes("submit") ||
        aria.includes("send") ||
        aria.includes("submit") ||
        title.includes("send") ||
        title.includes("submit") ||
        cls.includes("submit")
      );
    });

    const submitButton =
      semanticButton || (candidates.length ? candidates[candidates.length - 1] : null);

    if (submitButton) {
      submitButton.click();
      window.setTimeout(() => submitButton.click(), 120);
      return;
    }

    const form = chatInput.closest("form");
    if (form && typeof form.requestSubmit === "function") {
      form.requestSubmit();
      return;
    }

    chatInput.focus();
    ["keydown", "keypress", "keyup"].forEach((eventName) => {
      chatInput.dispatchEvent(
        new KeyboardEvent(eventName, {
          key: "Enter",
          code: "Enter",
          bubbles: true,
        })
      );
    });
  }

  function syncKnowledgeGraphFocus() {
    const graphPanel = document.querySelector("#knowledge-graph-plot");
    if (!graphPanel) {
      return;
    }
    const focusedCard = graphPanel.querySelector(
      ".kg-file-card.is-focused, .kg-tree-item--file.is-focused"
    );
    if (!focusedCard || focusedCard.dataset.kgFocused === "true") {
      return;
    }
    focusedCard.dataset.kgFocused = "true";
    window.setTimeout(() => {
      focusedCard.scrollIntoView({
        block: "nearest",
        inline: "nearest",
        behavior: "smooth",
      });
    }, 40);
  }

  function bindKnowledgeGraphPan() {
    const graphPanel = document.querySelector("#knowledge-graph-plot");
    if (!graphPanel) {
      return;
    }

    const shell = graphPanel.querySelector(".knowledge-graph-shell");
    if (!shell || shell.dataset.kgDragBound === "true") {
      return;
    }
    shell.dataset.kgDragBound = "true";

    let isPointerDown = false;
    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let startScrollLeft = 0;
    let startScrollTop = 0;
    let suppressClick = false;
    const DRAG_THRESHOLD = 8;

    const clearDragState = () => {
      isPointerDown = false;
      isDragging = false;
      shell.classList.remove("is-dragging");
      shell.style.cursor = "";
    };

    const stopTracking = () => {
      if (!isPointerDown && !isDragging) {
        return;
      }
      if (isDragging) {
        window.setTimeout(() => {
          suppressClick = false;
        }, 120);
      } else {
        suppressClick = false;
      }
      clearDragState();
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp, true);
      window.removeEventListener("pointercancel", handlePointerCancel, true);
    };

    const handlePointerMove = (event) => {
      if (!isPointerDown) {
        return;
      }

      const deltaX = event.clientX - startX;
      const deltaY = event.clientY - startY;
      if (!isDragging) {
        if (Math.abs(deltaX) < DRAG_THRESHOLD && Math.abs(deltaY) < DRAG_THRESHOLD) {
          return;
        }
        isDragging = true;
        suppressClick = true;
        shell.classList.add("is-dragging");
        shell.style.cursor = "grabbing";
      }

      shell.scrollLeft = startScrollLeft - deltaX;
      shell.scrollTop = startScrollTop - deltaY;
      event.preventDefault();
    };

    const handlePointerUp = () => {
      stopTracking();
    };

    const handlePointerCancel = () => {
      stopTracking();
    };

    shell.addEventListener(
      "click",
      (event) => {
        if (!suppressClick) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        if (typeof event.stopImmediatePropagation === "function") {
          event.stopImmediatePropagation();
        }
      },
      true
    );

    shell.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) {
        return;
      }
      if (event.target.closest("input, textarea, select")) {
        return;
      }

      isPointerDown = true;
      isDragging = false;
      suppressClick = false;
      startX = event.clientX;
      startY = event.clientY;
      startScrollLeft = shell.scrollLeft;
      startScrollTop = shell.scrollTop;
      window.addEventListener("pointermove", handlePointerMove);
      window.addEventListener("pointerup", handlePointerUp, true);
      window.addEventListener("pointercancel", handlePointerCancel, true);
    });

    shell.addEventListener("pointerleave", () => {
      if (!isPointerDown) {
        return;
      }
      stopTracking();
    });
  }

  function bindKnowledgeGraphViewer() {
    const graphPanel = document.querySelector("#knowledge-graph-plot");
    const shell = graphPanel?.querySelector(".knowledge-graph-shell");
    const overlay = shell?.querySelector("[data-kg-viewer-overlay='true']");
    const dialog = overlay?.querySelector(".kg-viewer-dialog");
    const viewport = overlay?.querySelector("[data-kg-viewer-viewport='true']");
    const stage = overlay?.querySelector("[data-kg-viewer-stage='true']");
    const utils = globalThis.KnowledgeGraphViewerUtils;

    if (
      !graphPanel ||
      !shell ||
      !overlay ||
      !dialog ||
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
    let suppressClick = false;

    const applyStageTransform = () => {
      stage.style.transform = `translate(${viewState.translateX}px, ${viewState.translateY}px) scale(${viewState.scale})`;
      stage.setAttribute("data-kg-scale", String(viewState.scale));
    };

    const fitViewer = () => {
      const previousTransform = stage.style.transform;
      stage.style.transform = "translate(0px, 0px) scale(1)";
      const viewportRect = viewport.getBoundingClientRect();
      const contentWidth = Math.max(stage.scrollWidth || 0, stage.offsetWidth || 0, 1);
      const contentHeight = Math.max(stage.scrollHeight || 0, stage.offsetHeight || 0, 1);
      viewState = utils.computeFittedTransform({
        viewportWidth: viewportRect.width || viewport.clientWidth || 1,
        viewportHeight: viewportRect.height || viewport.clientHeight || 1,
        contentWidth,
        contentHeight,
        padding: 40,
        minScale: 0.35,
        maxScale: 2.5,
      });
      if (!previousTransform && !Number.isFinite(viewState.scale)) {
        viewState = { scale: 1, translateX: 0, translateY: 0 };
      }
      applyStageTransform();
    };

    const openViewer = () => {
      overlay.hidden = false;
      shell.classList.add("is-viewer-open");
      document.body.classList.add("kg-viewer-open");
      window.requestAnimationFrame(() => {
        fitViewer();
      });
    };

    const closeViewer = () => {
      overlay.hidden = true;
      shell.classList.remove("is-viewer-open");
      document.body.classList.remove("kg-viewer-open");
      pointerState = null;
      suppressClick = false;
      viewport.classList.remove("is-dragging");
    };

    const queueClickReset = () => {
      window.setTimeout(() => {
        suppressClick = false;
      }, 140);
    };

    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) {
        closeViewer();
      }
    });

    shell.addEventListener("click", (event) => {
      const openTrigger = event.target.closest("[data-kg-open-viewer='true']");
      if (openTrigger) {
        event.preventDefault();
        openViewer();
        return;
      }

      const closeTrigger = event.target.closest("[data-kg-viewer-close='true']");
      if (closeTrigger) {
        event.preventDefault();
        closeViewer();
        return;
      }

      const actionTrigger = event.target.closest("[data-kg-viewer-action]");
      if (!actionTrigger) {
        return;
      }
      event.preventDefault();

      const action = actionTrigger.getAttribute("data-kg-viewer-action") || "";
      if (action === "fit" || action === "reset") {
        fitViewer();
        return;
      }

      const midpoint = {
        cursorX: (viewport.clientWidth || 0) / 2,
        cursorY: (viewport.clientHeight || 0) / 2,
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
      "click",
      (event) => {
        if (!suppressClick) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        if (typeof event.stopImmediatePropagation === "function") {
          event.stopImmediatePropagation();
        }
        suppressClick = false;
      },
      true
    );

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
      if (event.button !== 0) {
        return;
      }
      pointerState = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        originX: viewState.translateX,
        originY: viewState.translateY,
        didDrag: false,
      };
      suppressClick = false;
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
      suppressClick = true;
      viewport.classList.add("is-dragging");
      viewState.translateX = pointerState.originX + (event.clientX - pointerState.startX);
      viewState.translateY = pointerState.originY + (event.clientY - pointerState.startY);
      applyStageTransform();
      event.preventDefault();
    });

    const clearPointerState = (event) => {
      if (!pointerState || event.pointerId !== pointerState.pointerId) {
        return;
      }
      if (viewport.hasPointerCapture?.(event.pointerId)) {
        viewport.releasePointerCapture(event.pointerId);
      }
      if (pointerState.didDrag) {
        queueClickReset();
      } else {
        suppressClick = false;
      }
      pointerState = null;
      viewport.classList.remove("is-dragging");
    };

    viewport.addEventListener("pointerup", clearPointerState);
    viewport.addEventListener("pointercancel", clearPointerState);

    if (!globalThis._ktemKnowledgeGraphEscapeBound) {
      document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") {
          return;
        }
        document
          .querySelectorAll("[data-kg-viewer-overlay='true']")
          .forEach((node) => {
            if (!(node instanceof HTMLElement) || node.hidden) {
              return;
            }
            node.hidden = true;
          });
        document
          .querySelectorAll(".knowledge-graph-shell.is-viewer-open")
          .forEach((node) => node.classList.remove("is-viewer-open"));
        document.body.classList.remove("kg-viewer-open");
      });
      globalThis._ktemKnowledgeGraphEscapeBound = true;
    }
  }

  function applyIconOnlyButtonTooltips() {
    const iconButtonHints = {
      "new-conv-button": "Start a new chat",
      "rename-conv-button": "Rename this chat",
      "delete-conv-button": "Delete this chat",
      "info-expand-button": "Expand or collapse the right panel",
      "chat-expand-button": "Expand or collapse the chat panel",
      "toggle-dark-button": "Toggle theme",
    };

    Object.entries(iconButtonHints).forEach(([id, label]) => {
      const button = document.getElementById(id);
      if (!button) {
        return;
      }
      button.setAttribute("title", label);
      button.setAttribute("aria-label", label);
    });

    // Fallback for icon-only buttons that are injected by Gradio without a title.
    document.querySelectorAll("button").forEach((button) => {
      if (button.getAttribute("title")) {
        return;
      }
      const hasVisibleText = (button.textContent || "").trim().length > 0;
      const hasIconContent = !!button.querySelector("img, svg");
      if (hasVisibleText || !hasIconContent) {
        return;
      }

      const fallbackLabel = button.getAttribute("aria-label") || "Icon button";
      button.setAttribute("title", fallbackLabel);
      if (!button.getAttribute("aria-label")) {
        button.setAttribute("aria-label", fallbackLabel);
      }
    });
  }

  function localizeUploadDropzoneText() {
    const replacements = [
      [new RegExp("\\u5c06\\u6587\\u4ef6\\u62d6\\u653e\\u5230\\u6b64\\u5904", "g"), "Drop files here"],
      [new RegExp("[\\-\\u2013\\u2014\\uff0d]\\s*\\u6216\\s*[\\-\\u2013\\u2014\\uff0d]", "g"), "- or -"],
      [new RegExp("\\u70b9\\u51fb\\u4e0a\\u4f20", "g"), "Click to upload"],
    ];

    const replaceTextNodes = (root) => {
      if (!root) {
        return;
      }
      const textWalker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let textNode = textWalker.nextNode();
      while (textNode) {
        const originalValue = textNode.nodeValue || "";
        let updatedValue = originalValue;
        replacements.forEach(([pattern, replacement]) => {
          updatedValue = updatedValue.replace(pattern, replacement);
        });
        if (updatedValue !== originalValue) {
          textNode.nodeValue = updatedValue;
        }
        textNode = textWalker.nextNode();
      }
    };

    document.querySelectorAll("input[data-testid='file-upload']").forEach((input) => {
      const uploadButton = input.closest("button");
      if (!uploadButton) {
        return;
      }
      replaceTextNodes(uploadButton);

      // Ensure the separator in the upload prompt is normalized even when Gradio splits text nodes.
      uploadButton.querySelectorAll("span.or").forEach((separator) => {
        const value = (separator.textContent || "").trim();
        if (value.includes("\u6216")) {
          separator.textContent = "- or -";
        }
      });

      uploadButton.setAttribute("title", "Upload files");
      uploadButton.setAttribute("aria-label", "Upload files");
    });
  }

  function cleanupKnowledgeGraphOverlayNodes() {
    const graphPanel = document.querySelector("#knowledge-graph-plot");
    if (!graphPanel) {
      return;
    }

    const proseNodes = graphPanel.querySelectorAll(".prose");
    proseNodes.forEach((node) => {
      const hasGraphShell = !!node.querySelector(".knowledge-graph-shell");
      const textContent = (node.textContent || "").trim();
      const shouldMask = !hasGraphShell && !textContent;

      // Do not remove Gradio-managed wrappers; only hide truly empty overlays.
      node.classList.toggle("kg-prose-empty", shouldMask);
    });
  }

  function cleanupHtmlInfoPanelOverlay() {
    const infoPanel = document.querySelector("#html-info-panel");
    if (!infoPanel) {
      return;
    }

    const proseNodes = infoPanel.querySelectorAll(".prose");
    const hasRenderableProseContent = Array.from(proseNodes).some((node) => {
      const textContent = (node.textContent || "").trim();
      if (textContent) {
        return true;
      }
      return !!node.querySelector(
        "details, p, li, table, img, svg, canvas, iframe, .evidence-content, .markmap"
      );
    });

    const fallbackText = (infoPanel.textContent || "").trim();
    const hasFallbackRenderableContent = !!infoPanel.querySelector(
      "details, p, li, table, img, svg, canvas, iframe, .evidence-content, .markmap"
    );
    const shouldCollapse =
      !hasRenderableProseContent && !fallbackText && !hasFallbackRenderableContent;

    // Collapse only truly empty info panels to avoid blocking KG node clicks.
    infoPanel.classList.toggle("kg-info-empty", shouldCollapse);
  }

  function bindKnowledgeGraphInteractions() {
    applyIconOnlyButtonTooltips();
    localizeUploadDropzoneText();
    cleanupKnowledgeGraphOverlayNodes();
    cleanupHtmlInfoPanelOverlay();
    bindKnowledgeGraphViewer();

    const graphPanel = document.querySelector("#knowledge-graph-plot");
    if (graphPanel && graphPanel.dataset.kgBound !== "true") {
      graphPanel.dataset.kgBound = "true";
      graphPanel.addEventListener("click", (event) => {
        const toggleTrigger = event.target.closest("[data-kg-toggle-points]");
        if (toggleTrigger) {
          const fileCard = toggleTrigger.closest("[data-kg-file-card]");
          if (!fileCard) {
            return;
          }
          const isExpanded = fileCard.classList.toggle("is-points-expanded");
          const moreLabel =
            toggleTrigger.getAttribute("data-kg-more-label") ||
            toggleTrigger.textContent ||
            "";
          const lessLabel =
            toggleTrigger.getAttribute("data-kg-less-label") || "Show less";

          toggleTrigger.setAttribute("aria-expanded", isExpanded ? "true" : "false");
          toggleTrigger.textContent = isExpanded ? lessLabel : moreLabel;
          return;
        }

        const trigger = event.target.closest("[data-kg-payload]");
        if (!trigger) {
          return;
        }

        let payload = trigger.getAttribute("data-kg-payload");
        if (!payload) {
          return;
        }

        try {
          payload = JSON.parse(payload);
        } catch (error) {
          payload = null;
        }

        if (!payload || typeof payload !== "object") {
          return;
        }

        const graphContext = payload.graph_context || {};
        setKnowledgeGraphContext(JSON.stringify(graphContext));
        graphPanel
          .querySelectorAll(".kg-tree-node.is-selected")
          .forEach((node) => node.classList.remove("is-selected"));
        if (trigger.classList.contains("kg-tree-node")) {
          trigger.classList.add("is-selected");
        }
        renderKnowledgeGraphAnswerHint(payload);
        const fillQuestion = String(
          payload.fill_question || payload.suggested_question || payload.prompt || ""
        ).trim();
        if (fillQuestion) {
          fillChatInputWithoutSubmit(fillQuestion);
        }
      });
    }

    const answerHint = document.querySelector("#kg-answer-hint");
    if (answerHint && answerHint.dataset.kgHintBound !== "true") {
      answerHint.dataset.kgHintBound = "true";
      answerHint.addEventListener("click", (event) => {
        const trigger = event.target.closest("[data-kg-fill-question]");
        if (!trigger) {
          return;
        }
        const question = trigger.getAttribute("data-kg-fill-question") || "";
        if (!question) {
          return;
        }
        fillChatInputWithoutSubmit(question);
      });
    }

    const fileList = document.querySelector("#chat-file-list");
    if (fileList && fileList.dataset.chatFileBound !== "true") {
      fileList.dataset.chatFileBound = "true";
      fileList.addEventListener("click", (event) => {
        const trigger = event.target.closest("[data-chat-file-id]");
        if (!trigger) {
          return;
        }
        const fileId = trigger.getAttribute("data-chat-file-id") || "";
        if (!fileId) {
          return;
        }
        setChatFileClick(fileId);
      });
    }
    syncKnowledgeGraphFocus();
  }

  function ensureSelectionPrompt() {
    if (selectionPromptBox) {
      return;
    }

    selectionPromptBox = document.createElement("div");
    selectionPromptBox.id = "ktem-selection-prompt";
    selectionPromptBox.style.position = "fixed";
    selectionPromptBox.style.zIndex = "9999";
    selectionPromptBox.style.display = "none";
    selectionPromptBox.style.width = "420px";
    selectionPromptBox.style.maxWidth = "min(420px, calc(100vw - 24px))";
    selectionPromptBox.style.background = "var(--input-background-fill, var(--background-fill-primary, #fff))";
    selectionPromptBox.style.border = "1px solid var(--border-color-primary, #d4d4d8)";
    selectionPromptBox.style.borderRadius = "10px";
    selectionPromptBox.style.boxShadow = "0 8px 20px rgba(0,0,0,0.12)";
    selectionPromptBox.style.padding = "8px";
    selectionPromptBox.style.backdropFilter = "blur(4px)";
    selectionPromptBox.style.boxSizing = "border-box";
    selectionPromptBox.innerHTML = `
      <div style="display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:6px;">
        <strong style="font-size:12px; color: var(--body-text-color, inherit);">Ask About Selection</strong>
        <button id="ktem-selection-close" type="button" style="border:none;background:transparent;cursor:pointer;font-size:14px;line-height:1;color:var(--body-text-color-subdued,inherit);">x</button>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <input id="ktem-selection-question" type="text" placeholder="Ask a question about this selected text" style="flex:1 1 auto;min-width:0;height:34px;box-sizing:border-box;border:1px solid var(--border-color-primary,#d4d4d8);border-radius:8px;padding:0 10px;font-size:13px;background:var(--input-background-fill,#fff);color:var(--body-text-color,inherit);" />
        <button id="ktem-selection-ask" type="button" style="height:34px;padding:0 12px;border-radius:8px;border:1px solid var(--border-color-primary,#d4d4d8);cursor:pointer;background:var(--button-primary-background-fill,var(--background-fill-secondary,#f4f4f5));color:var(--button-primary-text-color,var(--body-text-color,inherit));white-space:nowrap;">Ask</button>
      </div>
    `;
    document.body.appendChild(selectionPromptBox);

    selectionPromptInput = selectionPromptBox.querySelector("#ktem-selection-question");
    selectionPromptAsk = selectionPromptBox.querySelector("#ktem-selection-ask");
    selectionPromptClose = selectionPromptBox.querySelector("#ktem-selection-close");

    if (selectionPromptInput) {
      selectionPromptInput.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") {
          return;
        }
        // Avoid sending while IME composition (e.g. Chinese input) is active.
        if (event.isComposing || event.keyCode === 229) {
          return;
        }
        event.preventDefault();
        selectionPromptAsk?.click();
      });
    }

    selectionPromptClose.onclick = () => {
      hideSelectionPrompt();
      setSelectedPageText("");
      currentSelectedPageText = "";
    };
    selectionPromptAsk.onclick = () => {
      const question = (selectionPromptInput?.value || "").trim();
      const chatInput = getChatInputField();
      if (!chatInput) {
        return;
      }

      const baseQuestion = question || "Please explain this selected text.";
      const selectedBlock = getSelectedPageTextValue();
      setKnowledgeGraphContext("");
      if (selectedBlock) {
        currentSelectedPageText = selectedBlock;
        setSelectedPageText(selectedBlock);
        chatInput.value =
          `${baseQuestion}\n\n[Selected text from current page]\n${selectedBlock}`;
      } else {
        chatInput.value = baseQuestion;
      }
      chatInput.dispatchEvent(new Event("input", { bubbles: true }));
      chatInput.dispatchEvent(new Event("change", { bubbles: true }));
      window.setTimeout(() => submitChatInput(), 0);
      hideSelectionPrompt();
    };
  }

  function hideSelectionPrompt() {
    if (!selectionPromptBox) {
      return;
    }
    selectionPromptBox.style.display = "none";
    if (selectionPromptInput) {
      selectionPromptInput.value = "";
    }
  }

  function showSelectionPromptNearRect(rectInIframe) {
    ensureSelectionPrompt();
    const iframe = document.getElementById("main-pdf-preview-frame");
    if (!selectionPromptBox || !iframe) {
      return;
    }

    const iframeRect = iframe.getBoundingClientRect();
    const rect = rectInIframe || { left: 0, top: 0, width: 0, height: 0 };
    const baseLeft = iframeRect.left + (rect.left || 0);
    const baseTop = iframeRect.top + (rect.top || 0) + (rect.height || 0) + 8;

    let left = Math.max(12, baseLeft);
    let top = Math.max(12, baseTop);
    const boxWidth = 420;
    const boxHeight = 96;
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;

    if (left + boxWidth > viewportWidth - 12) {
      left = Math.max(12, viewportWidth - boxWidth - 12);
    }
    if (top + boxHeight > viewportHeight - 12) {
      top = Math.max(12, iframeRect.top + (rect.top || 0) - boxHeight - 8);
    }

    selectionPromptBox.style.left = `${left}px`;
    selectionPromptBox.style.top = `${top}px`;
    selectionPromptBox.style.display = "block";
    if (selectionPromptInput) {
      selectionPromptInput.focus();
    }
  }

  function isSelectionPromptVisible() {
    return !!selectionPromptBox && selectionPromptBox.style.display !== "none";
  }

  function getCurrentPageNumber() {
    const pageFields = document.querySelectorAll(
      "#pdf-page-number input, #pdf-page-number textarea"
    );
    if (!pageFields || pageFields.length === 0) {
      return null;
    }
    for (let i = pageFields.length - 1; i >= 0; i--) {
      const value = (pageFields[i]?.value || "").trim();
      const page = parseInt(value, 10);
      if (Number.isFinite(page) && page > 0) {
        return page;
      }
    }
    return null;
  }

  function initMainShellLayout() {
    const mainParent = document.getElementById("chat-tab")?.parentNode;
    if (!mainParent) {
      return;
    }

    if (mainParent.childNodes?.[0]?.classList) {
      mainParent.childNodes[0].classList.add("header-bar");
    }
    mainParent.style = "padding: 0; margin: 0; position: relative";
    if (mainParent.parentNode) {
      mainParent.parentNode.style = "gap: 0";
      if (mainParent.parentNode.parentNode) {
        mainParent.parentNode.parentNode.style = "padding: 0";
      }
    }

    let versionNode = document.getElementById("app-version-badge");
    if (!versionNode) {
      versionNode = document.createElement("p");
      versionNode.id = "app-version-badge";
      mainParent.appendChild(versionNode);
    }
    versionNode.textContent = "version: KH_APP_VERSION";

    const darkToggle = document.getElementById("toggle-dark-button");
    if (darkToggle) {
      darkToggle.style.display = "none";
    }

    const favicon = document.createElement("link");
    favicon.rel = "icon";
    favicon.type = "image/svg+xml";
    favicon.href = "/favicon.ico";
    document.head.appendChild(favicon);

    const convDropdown = document.querySelector("#conversation-dropdown input");
    if (convDropdown) {
      convDropdown.placeholder = "Browse conversation";
    }
  }

  function initChatPanelControls() {
    const infoExpandButton = document.getElementById("info-expand-button");
    const chatInfoPanel = document.getElementById("info-expand");
    if (infoExpandButton && chatInfoPanel) {
      const infoExpandHeader = chatInfoPanel.querySelector(":scope > div:first-child");
      if (infoExpandHeader) {
        infoExpandHeader.appendChild(infoExpandButton);
      }
    }

    const chatExpandButton = document.getElementById("chat-expand-button");
    const chatColumn = document.getElementById("chat-area");
    const convColumn = document.getElementById("conv-settings-panel");

    const settingTabNavBar = document.querySelector("#settings-tab .tab-nav");
    const settingCloseButton = document.getElementById("save-setting-btn");
    if (settingCloseButton && settingTabNavBar) {
      settingTabNavBar.appendChild(settingCloseButton);
    }

    const defaultConvColumnMinWidth = "min(300px, 100%)";
    if (convColumn) {
      convColumn.style.minWidth = defaultConvColumnMinWidth;
    }

    globalThis.toggleChatColumn = () => {
      if (!convColumn) {
        return;
      }
      const flexGrow = convColumn.style.flexGrow;
      if (flexGrow == "0") {
        convColumn.style.flexGrow = "1";
        convColumn.style.minWidth = defaultConvColumnMinWidth;
      } else {
        convColumn.style.flexGrow = "0";
        convColumn.style.minWidth = "0px";
      }
    };

    if (chatColumn && chatExpandButton && chatExpandButton.offsetParent !== null) {
      chatExpandButton.style.flexGrow = "0";
      chatExpandButton.style.width = "36px";
      chatExpandButton.style.minWidth = "36px";
      chatExpandButton.style.height = "36px";
      chatExpandButton.style.padding = "0";
      chatColumn.insertBefore(chatExpandButton, chatColumn.firstChild);
    }
  }

  function initReportControls() {
    const reportDiv = document.querySelector(
      "#report-accordion > div:nth-child(3) > div:nth-child(1)"
    );
    const shareConvCheckbox = document.getElementById("is-public-checkbox");
    if (shareConvCheckbox && reportDiv) {
      reportDiv.insertBefore(shareConvCheckbox, reportDiv.querySelector("button"));
    }

    const isPublicCheckbox = document.getElementById("suggest-chat-checkbox");
    if (!isPublicCheckbox) {
      return;
    }
    const labelElement = isPublicCheckbox.getElementsByTagName("label")[0];
    const checkboxSpan = isPublicCheckbox.getElementsByTagName("span")[0];
    const newDiv = document.createElement("div");
    if (!labelElement || !checkboxSpan) {
      return;
    }

    labelElement.classList.add("switch");
    isPublicCheckbox.appendChild(checkboxSpan);
    labelElement.appendChild(newDiv);
  }

  syncMainPdfPreview();
  initMainShellLayout();
  initChatPanelControls();
  initReportControls();

  // clpse
  globalThis.clpseFn = (id) => {
    var obj = document.getElementById("clpse-btn-" + id);
    obj.classList.toggle("clpse-active");
    var content = obj.nextElementSibling;
    if (content.style.display === "none") {
      content.style.display = "block";
    } else {
      content.style.display = "none";
    }
  };

  // store info in local storage
  globalThis.setStorage = (key, value) => {
    localStorage.setItem(key, value);
  };
  globalThis.getStorage = (key, value) => {
    const item = localStorage.getItem(key);
    return item ? item : value;
  };
  globalThis.removeFromStorage = (key) => {
    localStorage.removeItem(key);
  };

  // Function to scroll to given citation with ID
  // Sleep function using Promise and setTimeout
  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  globalThis.scrollToCitation = async (event) => {
    event.preventDefault(); // Prevent the default link behavior
    var citationId = event.target.getAttribute("id");

    await sleep(100); // Sleep for 100 milliseconds

    // check if modal is open
    var modal = document.getElementById("pdf-modal");
    var citation = document.querySelector('mark[id="' + citationId + '"]');

    if (modal.style.display == "block") {
      // trigger on click event of PDF Preview link
      var detail_elem = citation;
      // traverse up the DOM tree to find the parent element with tag detail
      while (detail_elem.tagName.toLowerCase() != "details") {
        detail_elem = detail_elem.parentElement;
      }
      detail_elem.getElementsByClassName("pdf-link").item(0).click();
    } else {
      if (citation) {
        citation.scrollIntoView({ behavior: "smooth" });
      }
    }
  };

  globalThis.fullTextSearch = () => {
    try {
      if (typeof MiniSearch === "undefined") {
        return;
      }

    // Assign text selection event to last bot message
    var bot_messages = document.querySelectorAll(
      "div#main-chat-bot div.message-row.bot-row"
    );
    if (!bot_messages || bot_messages.length === 0) {
      return;
    }
    var last_bot_message = bot_messages[bot_messages.length - 1];
    if (!last_bot_message || !last_bot_message.classList) {
      return;
    }

    // check if the last bot message has class "text_selection"
    if (last_bot_message.classList.contains("text_selection")) {
      return;
    }

    // assign new class to last message
    last_bot_message.classList.add("text_selection");

    // Get sentences from evidence div
    var evidences = document.querySelectorAll(
      "#html-info-panel > div:last-child > div > details.evidence div.evidence-content"
    );

    const segmenterEn = new Intl.Segmenter("en", { granularity: "sentence" });
    // Split sentences and save to all_segments list
    var all_segments = [];
    for (var evidence of evidences) {
      // check if <details> tag is open
      if (!evidence.parentElement.open) {
        continue;
      }
      var markmap_div = evidence.querySelector("div.markmap");
      if (markmap_div) {
        continue;
      }

      var evidence_content = evidence.textContent.replace(/[\r\n]+/g, " ");
      const sentenceIterator = segmenterEn
        .segment(evidence_content)
        [Symbol.iterator]();
      let sentence = sentenceIterator.next().value;
      while (sentence) {
        const segment = sentence.segment.trim();
        if (segment) {
          all_segments.push({
            id: all_segments.length,
            text: segment,
          });
        }
        sentence = sentenceIterator.next().value;
      }
    }

    let miniSearch = new MiniSearch({
      fields: ["text"], // fields to index for full-text search
      storeFields: ["text"],
    });

    // Index all documents
    miniSearch.addAll(all_segments);

    last_bot_message.addEventListener("mouseup", () => {
      let selection = window.getSelection().toString();
      if (!selection || !selection.trim()) {
        return;
      }
      let results = miniSearch.search(selection);

      if (results.length == 0) {
        return;
      }
      let matched_text = results[0].text;

      var evidences = document.querySelectorAll(
        "#html-info-panel > div:last-child > div > details.evidence div.evidence-content"
      );
      // check if modal is open
      var modal = document.getElementById("pdf-modal");

      // convert all <mark> in evidences to normal text
      evidences.forEach((evidence) => {
        evidence.querySelectorAll("mark").forEach((mark) => {
          mark.outerHTML = mark.innerText;
        });
      });

      // highlight matched_text in evidences
      for (var evidence of evidences) {
        var evidence_content = evidence.textContent.replace(/[\r\n]+/g, " ");
        if (evidence_content.includes(matched_text)) {
          // select all p and li elements
          const paragraphs = evidence.querySelectorAll("p, li");
          for (var p of paragraphs) {
            var p_content = p.textContent.replace(/[\r\n]+/g, " ");
            if (p_content.includes(matched_text)) {
              p.innerHTML = p_content.replace(
                matched_text,
                "<mark>" + matched_text + "</mark>"
              );
              if (modal.style.display == "block") {
                // trigger on click event of PDF Preview link
                var detail_elem = p;
                // traverse up the DOM tree to find the parent element with tag detail
                while (detail_elem.tagName.toLowerCase() != "details") {
                  detail_elem = detail_elem.parentElement;
                }
                detail_elem.getElementsByClassName("pdf-link").item(0).click();
              } else {
                p.scrollIntoView({ behavior: "smooth", block: "center" });
              }
              break;
            }
          }
        }
      }
    });
    } catch (error) {
      // Ignore optional full-text enhancement errors.
    }
  };

  globalThis.spawnDocument = (content, options) => {
    let opt = {
      window: "",
      closeChild: true,
      childId: "_blank",
    };
    Object.assign(opt, options);
    // minimal error checking
    if (
      content &&
      typeof content.toString == "function" &&
      content.toString().length
    ) {
      let child = window.open("", opt.childId, opt.window);
      child.document.write(content.toString());
      if (opt.closeChild) child.document.close();
      return child;
    }
  };

  globalThis.fillChatInput = (event) => {
    let chatInput = document.querySelector("#chat-input textarea");
    if (!chatInput) {
      return;
    }
    // fill the chat input with the clicked div text
    setKnowledgeGraphContext("");
    chatInput.value = "Explain " + event.target.textContent;
    chatInput.dispatchEvent(new Event("input", { bubbles: true }));
    chatInput.focus();
  };

  bindKnowledgeGraphInteractions();
  enforceAnswerPanelScroll();
  if (!globalThis._ktemSelectionBridgeRegistered) {
    window.addEventListener("message", (event) => {
      if (event.origin !== window.location.origin) {
        return;
      }

      if (event.data?.type === "ktem-pdf-zoom-updated") {
        if (isOfficePreview) {
          const zoom = parseFloat(event.data.zoom || "");
          if (Number.isFinite(zoom) && zoom > 0) {
            updateOfficeZoomControl(zoom);
          }
        }
        return;
      }

      if (event.data?.type !== "ktem-pdf-text-selection") {
        return;
      }

      let selectedText = (event.data.text || "").trim();
      let selectedPage = parseInt(event.data.page || "", 10);
      let currentPage = getCurrentPageNumber();

      if (
        Number.isFinite(selectedPage) &&
        Number.isFinite(currentPage) &&
        selectedPage !== currentPage
      ) {
        return;
      }

      if (selectedText.length > 2000) {
        selectedText = selectedText.slice(0, 2000);
      }
      if (!selectedText) {
        // Ignore transient empty-selection events right after a valid selection.
        if (Date.now() - lastNonEmptySelectionTs < 350) {
          return;
        }
        currentSelectedPageText = "";
        setSelectedPageText("");
        hideSelectionPrompt();
        return;
      }
      currentSelectedPageText = selectedText;
      setSelectedPageText(selectedText);
      lastNonEmptySelectionTs = Date.now();
      showSelectionPromptNearRect(event.data.rect);
    });
    globalThis._ktemSelectionBridgeRegistered = true;
  }

  if (!globalThis._ktemSelectionPromptOutsideCloseRegistered) {
    document.addEventListener("mousedown", (event) => {
      if (!isSelectionPromptVisible()) {
        return;
      }
      const target = event.target;
      if (selectionPromptBox && selectionPromptBox.contains(target)) {
        return;
      }
      hideSelectionPrompt();
    });
    globalThis._ktemSelectionPromptOutsideCloseRegistered = true;
  }

  if (!answerPanelObserver) {
    answerPanelObserver = new MutationObserver(() => {
      enforceAnswerPanelScroll();
      bindKnowledgeGraphInteractions();
    });

    answerPanelObserver.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    globalThis._ktemAnswerPanelObserver = answerPanelObserver;
  }

  if (!knowledgeGraphObserver) {
    knowledgeGraphObserver = new MutationObserver(() => {
      bindKnowledgeGraphInteractions();
    });
    knowledgeGraphObserver.observe(document.body, {
      childList: true,
      subtree: true,
    });
    globalThis._ktemKnowledgeGraphObserver = knowledgeGraphObserver;
  }

  if (!previewSrcPoller) {
    previewSrcPoller = window.setInterval(syncMainPdfPreview, 120);
    globalThis._ktemPreviewSrcPoller = previewSrcPoller;
  }
}

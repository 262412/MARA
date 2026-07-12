(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.KtemSafeDom = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const HIGHLIGHT_ATTRIBUTE = "data-ktem-search-highlight";
  const DOCUMENT_DATA_PREFIX = "data:text/html;charset=utf-8,";
  const DOCUMENT_CSP =
    "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; worker-src 'none'; base-uri 'none'; form-action 'none'";
  const BLOCKED_POPUP_ELEMENTS = new Set([
    "base",
    "button",
    "embed",
    "form",
    "iframe",
    "input",
    "link",
    "meta",
    "object",
    "script",
    "select",
    "textarea",
  ]);

  function normalizeSearchText(value) {
    return String(value || "").replace(/[\r\n]+/g, " ");
  }

  function splitTextForHighlight(text, searchText) {
    const source = String(text || "");
    const search = String(searchText || "");
    const index = search ? source.indexOf(search) : -1;
    if (index < 0) {
      return null;
    }
    return {
      before: source.slice(0, index),
      match: source.slice(index, index + search.length),
      after: source.slice(index + search.length),
    };
  }

  function previewPolicy(mode) {
    const scriptsRequired = mode === "pdf";
    return {
      sandbox: scriptsRequired
        ? "allow-scripts allow-same-origin"
        : "allow-same-origin",
      referrerPolicy: "no-referrer",
    };
  }

  function previewModeForSource(source, origin, trustedPdfViewerPath) {
    const value = String(source || "").trim();
    if (!value) {
      return "invalid";
    }
    if (/^data:image\/(?:png|jpeg|gif|webp);base64,[a-z0-9+/]+={0,2}$/i.test(value)) {
      return "image";
    }
    if (value.toLowerCase().startsWith(DOCUMENT_DATA_PREFIX)) {
      return "document";
    }
    try {
      const candidate = new URL(value, origin);
      const trustedViewer = new URL(trustedPdfViewerPath, origin);
      if (
        candidate.origin === origin &&
        trustedViewer.origin === origin &&
        candidate.pathname === trustedViewer.pathname &&
        isSafePdfFileParameter(candidate, origin, value)
      ) {
        return "pdf";
      }
    } catch (error) {
      return "invalid";
    }
    return "invalid";
  }

  function isSafePdfFileParameter(candidate, origin, rawSource) {
    if (
      candidate.username ||
      candidate.password ||
      String(rawSource).includes("\\") ||
      candidate.searchParams.getAll("file").length !== 1
    ) {
      return false;
    }
    const fileValue = candidate.searchParams.get("file") || "";
    if (!fileValue || fileValue.startsWith("//") || fileValue.includes("\\")) {
      return false;
    }
    let decoded = fileValue;
    try {
      for (let index = 0; index < 2; index += 1) {
        decoded = decodeURIComponent(decoded);
      }
    } catch (error) {
      return false;
    }
    if (/(?:^|[=/])\.\.(?:[/]|$)/.test(decoded)) {
      return false;
    }
    try {
      const fileUrl = new URL(fileValue, origin);
      return (
        !fileUrl.username &&
        !fileUrl.password &&
        fileUrl.origin === origin &&
        /\/(?:gradio_api\/)?file=/.test(fileUrl.pathname)
      );
    } catch (error) {
      return false;
    }
  }

  function lockedDocumentSrcdoc(source) {
    const value = String(source || "").trim();
    if (!value.toLowerCase().startsWith(DOCUMENT_DATA_PREFIX)) {
      return "";
    }
    let content = "";
    try {
      content = decodeURIComponent(value.slice(DOCUMENT_DATA_PREFIX.length));
    } catch (error) {
      return "";
    }
    return (
      "<!doctype html><html><head><meta charset='utf-8'>" +
      '<meta http-equiv="Content-Security-Policy" content="' +
      DOCUMENT_CSP +
      '"></head><body>' +
      content +
      "</body></html>"
    );
  }

  function setIframePolicy(iframe, mode) {
    if (!iframe || typeof iframe.setAttribute !== "function") {
      return;
    }
    const policy = previewPolicy(mode);
    if (iframe.getAttribute("sandbox") !== policy.sandbox) {
      iframe.setAttribute("sandbox", policy.sandbox);
    }
    if (iframe.getAttribute("referrerpolicy") !== policy.referrerPolicy) {
      iframe.setAttribute("referrerpolicy", policy.referrerPolicy);
    }
  }

  function replaceChildrenWithText(element, text) {
    if (!element || !element.ownerDocument) {
      return null;
    }
    const textNode = element.ownerDocument.createTextNode(String(text || ""));
    element.replaceChildren(textNode);
    return textNode;
  }

  function setTextHighlight(element, active) {
    if (!element || !element.ownerDocument) {
      return null;
    }
    const text = element.textContent || "";
    element.replaceChildren();
    if (!active) {
      return replaceChildrenWithText(element, text);
    }
    const highlight = element.ownerDocument.createElement("span");
    highlight.className = "highlight selected";
    highlight.appendChild(element.ownerDocument.createTextNode(text));
    element.appendChild(highlight);
    return highlight;
  }

  function shouldSkipTextNode(node, root) {
    let parent = node.parentElement;
    while (parent && parent !== root) {
      const tagName = String(parent.tagName || "").toLowerCase();
      if (
        tagName === "script" ||
        tagName === "style" ||
        tagName === "noscript" ||
        tagName === "textarea" ||
        parent.hasAttribute(HIGHLIGHT_ATTRIBUTE)
      ) {
        return true;
      }
      parent = parent.parentElement;
    }
    return false;
  }

  function collectNormalizedText(root) {
    const doc = root && root.ownerDocument;
    if (!doc || typeof doc.createTreeWalker !== "function") {
      return { text: "", locations: [] };
    }
    const nodeFilter = doc.defaultView?.NodeFilter || globalThis.NodeFilter;
    const showText = nodeFilter?.SHOW_TEXT || 4;
    const walker = doc.createTreeWalker(root, showText);
    const locations = [];
    let text = "";
    let pendingLineBreak = null;
    let node = walker.nextNode();

    while (node) {
      if (!shouldSkipTextNode(node, root)) {
        const value = node.data || "";
        for (let offset = 0; offset < value.length; offset += 1) {
          const character = value[offset];
          if (character === "\r" || character === "\n") {
            if (!pendingLineBreak) {
              pendingLineBreak = {
                start: { node, offset },
                end: { node, offset: offset + 1 },
              };
            } else {
              pendingLineBreak.end = { node, offset: offset + 1 };
            }
            continue;
          }
          if (pendingLineBreak) {
            text += " ";
            locations.push(pendingLineBreak);
            pendingLineBreak = null;
          }
          text += character;
          locations.push({
            start: { node, offset },
            end: { node, offset: offset + 1 },
          });
        }
      }
      node = walker.nextNode();
    }
    if (pendingLineBreak) {
      text += " ";
      locations.push(pendingLineBreak);
    }
    return { text, locations };
  }

  function highlightText(root, searchText) {
    const search = normalizeSearchText(searchText);
    if (!root || !search) {
      return null;
    }
    const collected = collectNormalizedText(root);
    const index = collected.text.indexOf(search);
    if (index < 0) {
      return null;
    }
    const start = collected.locations[index]?.start;
    const end = collected.locations[index + search.length - 1]?.end;
    if (!start || !end) {
      return null;
    }

    const range = root.ownerDocument.createRange();
    range.setStart(start.node, start.offset);
    range.setEnd(end.node, end.offset);
    const mark = root.ownerDocument.createElement("mark");
    mark.setAttribute(HIGHLIGHT_ATTRIBUTE, "true");
    mark.appendChild(range.extractContents());
    range.insertNode(mark);
    return mark;
  }

  function clearHighlights(root) {
    if (!root || typeof root.querySelectorAll !== "function") {
      return;
    }
    const selector = `mark[${HIGHLIGHT_ATTRIBUTE}]`;
    Array.from(root.querySelectorAll(selector)).forEach((mark) => {
      const parent = mark.parentNode;
      if (!parent) {
        return;
      }
      while (mark.firstChild) {
        parent.insertBefore(mark.firstChild, mark);
      }
      parent.removeChild(mark);
      if (typeof parent.normalize === "function") {
        parent.normalize();
      }
    });
  }

  function sanitizePopupTree(root) {
    const elements = [root, ...Array.from(root.querySelectorAll("*"))];
    elements.reverse().forEach((element) => {
      const tagName = String(element.tagName || "").toLowerCase();
      if (BLOCKED_POPUP_ELEMENTS.has(tagName)) {
        element.remove();
        return;
      }
      Array.from(element.attributes || []).forEach((attribute) => {
        const name = attribute.name.toLowerCase();
        const value = attribute.value.trim().toLowerCase();
        if (
          name.startsWith("on") ||
          name === "srcdoc" ||
          ((name === "href" || name === "xlink:href") &&
            (value.startsWith("javascript:") || value.startsWith("data:text/html")))
        ) {
          element.removeAttribute(attribute.name);
        }
      });
    });
  }

  function openSvgDocument(sourceSvg, options) {
    if (!sourceSvg || String(sourceSvg.tagName || "").toLowerCase() !== "svg") {
      return null;
    }
    const popupOptions = Object.assign(
      { window: "", childId: "_blank" },
      options || {}
    );
    const child = window.open("about:blank", popupOptions.childId, popupOptions.window);
    if (!child) {
      return null;
    }

    const doc = child.document;
    const html = doc.createElement("html");
    const head = doc.createElement("head");
    const meta = doc.createElement("meta");
    meta.httpEquiv = "Content-Security-Policy";
    meta.content =
      "default-src 'none'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; base-uri 'none'; form-action 'none'";
    const title = doc.createElement("title");
    title.textContent = "Mindmap";
    const style = doc.createElement("style");
    style.textContent = "html,body{margin:0;width:100%;height:100%}svg{width:100%;height:100vh}";
    const body = doc.createElement("body");
    const clone = doc.importNode(sourceSvg, true);
    sanitizePopupTree(clone);
    head.append(meta, title, style);
    body.appendChild(clone);
    html.append(head, body);
    doc.replaceChildren(html);
    child.opener = null;
    return child;
  }

  return {
    clearHighlights,
    highlightText,
    lockedDocumentSrcdoc,
    normalizeSearchText,
    openSvgDocument,
    previewPolicy,
    previewModeForSource,
    replaceChildrenWithText,
    setIframePolicy,
    setTextHighlight,
    splitTextForHighlight,
  };
});

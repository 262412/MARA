function onBlockLoad() {
  var infor_panel_scroll_pos = 0;
  var pdfJsViewerPath = "GR_FILE_ROOT_PATH/file=PDFJS_PREBUILT_DIR/web/viewer.html".replace(
    /\\/g,
    "/"
  );

  function getViewerInnerDoc(viewerId) {
    var viewer = document.getElementById(viewerId);
    if (!viewer) {
      return null;
    }

    return viewer.contentDocument
      ? viewer.contentDocument
      : viewer.contentWindow
        ? viewer.contentWindow.document
        : null;
  }

  function buildViewerSrc(src, page) {
    try {
      var viewerUrl = new URL(pdfJsViewerPath, window.location.origin);
      var pdfUrl = new URL(src, window.location.origin).toString();
      var pageNum = Math.max(1, parseInt(page || "1", 10) || 1);
      viewerUrl.searchParams.set("embed", "1");
      viewerUrl.searchParams.set("disablehistory", "true");
      viewerUrl.searchParams.set("sidebarviewonload", "0");
      viewerUrl.searchParams.set("ktempage", String(pageNum));
      viewerUrl.searchParams.set("ktemfit", "pdf");
      viewerUrl.searchParams.set("file", pdfUrl);
      viewerUrl.hash = "page=" + pageNum;
      return viewerUrl.toString();
    } catch (error) {
      return src || "";
    }
  }

  globalThis.createModal = () => {
    // Create modal for the 1st time if it does not exist
    var modal = document.getElementById("pdf-modal");
    if (!modal) {
      modal = document.createElement("div");
      document.body.appendChild(modal);
    }
    var old_position = null;
    var old_width = null;
    var old_left = null;
    var expanded = false;

    modal.id = "pdf-modal";
    modal.className = "modal";
    var modalContent = document.createElement("div");
    modalContent.className = "modal-content";
    var modalHeader = document.createElement("div");
    modalHeader.className = "modal-header";
    var closeButton = document.createElement("span");
    closeButton.className = "close";
    closeButton.id = "modal-close";
    closeButton.textContent = "×";
    var expandButton = document.createElement("span");
    expandButton.className = "close";
    expandButton.id = "modal-expand";
    expandButton.textContent = "⛶";
    var modalBody = document.createElement("div");
    modalBody.className = "modal-body";
    var pdfViewer = document.createElement("iframe");
    pdfViewer.id = "pdf-viewer";
    pdfViewer.title = "PDF preview";
    KtemSafeDom.setIframePolicy(pdfViewer, "pdf");
    pdfViewer.setAttribute("src", "about:blank");
    modalHeader.append(closeButton, expandButton);
    modalBody.appendChild(pdfViewer);
    modalContent.append(modalHeader, modalBody);
    modal.replaceChildren(modalContent);

    modal.querySelector("#modal-close").onclick = function () {
      modal.style.display = "none";
      var info_panel = document.getElementById("html-info-panel");
      if (info_panel) {
        info_panel.style.display = "block";
      }
      var scrollableDiv = document.getElementById("chat-info-panel");
      scrollableDiv.scrollTop = infor_panel_scroll_pos;
    };

    modal.querySelector("#modal-expand").onclick = function () {
      expanded = !expanded;
      if (expanded) {
        old_position = modal.style.position;
        old_left = modal.style.left;
        old_width = modal.style.width;

        modal.style.position = "fixed";
        modal.style.width = "70%";
        modal.style.left = "15%";
        modal.style.height = "100dvh";
      } else {
        modal.style.position = old_position;
        modal.style.width = old_width;
        modal.style.left = old_left;
        modal.style.height = "85dvh";
      }
    };
  };

  function matchRatio(str1, str2) {
    let n = str1.length;
    let m = str2.length;

    let lcs = [];
    for (let i = 0; i <= n; i++) {
      lcs[i] = [];
      for (let j = 0; j <= m; j++) {
        lcs[i][j] = 0;
      }
    }

    let result = "";
    let max = 0;
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < m; j++) {
        if (str1[i] === str2[j]) {
          lcs[i + 1][j + 1] = lcs[i][j] + 1;
          if (lcs[i + 1][j + 1] > max) {
            max = lcs[i + 1][j + 1];
            result = str1.substring(i - max + 1, i + 1);
          }
        }
      }
    }

    return result.length / Math.min(n, m);
  }

  globalThis.compareText = (search_phrases, page_label) => {
    var innerDoc = getViewerInnerDoc("pdf-viewer");
    if (!innerDoc) {
      setTimeout(() => compareText(search_phrases, page_label), 1000);
      return;
    }

    var renderedPages = innerDoc.querySelectorAll("div#viewer div.page");
    if (renderedPages.length == 0) {
      // if pages are not rendered yet, wait and try again
      setTimeout(() => compareText(search_phrases, page_label), 2000);
      return;
    }

    var query_selector =
      "#viewer > div[data-page-number='" +
      page_label +
      "'] > div.textLayer > span";
    var page_spans = innerDoc.querySelectorAll(query_selector);
    for (var i = 0; i < page_spans.length; i++) {
      var span = page_spans[i];
      if (
        span.textContent.length > 4 &&
        search_phrases.some(
          (phrase) => matchRatio(phrase, span.textContent) > 0.5
        )
      ) {
        KtemSafeDom.setTextHighlight(span, true);
      } else {
        // if span is already highlighted, remove it
        if (span.querySelector(".highlight")) {
          KtemSafeDom.setTextHighlight(span, false);
        }
      }
    }
  };

  // Sleep function using Promise and setTimeout
  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  // Function to open modal and display PDF
  globalThis.openModal = async (event) => {
    event.preventDefault();
    var target = event.currentTarget;
    var src = target.getAttribute("data-src");
    var page = target.getAttribute("data-page");
    var highlighted_spans =
      target.parentElement.parentElement.querySelectorAll("mark");

    // Get text from highlighted spans
    var search_phrases = Array.from(highlighted_spans).map(
      (span) => span.textContent
    );
    // Use regex to strip 【id】from search phrases
    search_phrases = search_phrases.map((phrase) =>
      phrase.replace(/【\d+】/g, "")
    );

    // var phrase = target.getAttribute("data-phrase");

    var pdfViewer = document.getElementById("pdf-viewer");
    var viewerSrc = buildViewerSrc(src, page);

    var currentSrc = pdfViewer.getAttribute("src");
    if (currentSrc !== viewerSrc) {
      pdfViewer.setAttribute("src", viewerSrc);
    }

    var scrollableDiv = document.getElementById("chat-info-panel");
    infor_panel_scroll_pos = scrollableDiv.scrollTop;

    var modal = document.getElementById("pdf-modal");
    modal.style.display = "block";
    var info_panel = document.getElementById("html-info-panel");
    if (info_panel) {
      info_panel.style.display = "none";
    }
    scrollableDiv.scrollTop = 0;

    /* search for text inside PDF page */
    await sleep(500);
    compareText(search_phrases, page);
  };

  globalThis.assignPdfOnclickEvent = () => {
    // Get all links and attach click event
    var links = document.getElementsByClassName("pdf-link");
    for (var i = 0; i < links.length; i++) {
      links[i].onclick = openModal;
    }
  };

  var created_modal = document.getElementById("pdf-viewer");
  if (!created_modal) {
    createModal();
  }
}

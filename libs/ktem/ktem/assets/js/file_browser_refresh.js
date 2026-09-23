(function (root) {
  "use strict";

  function createFileBrowserRefresh(document, newEpoch) {
    let mounted = null;
    let epoch = "";
    let filterVersion = 0;
    let viewVersion = 0;
    let catalogVersions = new Map();
    let selectorRequests = new Map();
    let appliedSelectors = new Map();
    let fileRequest = 0;
    let appliedFileRequest = 0;
    let uploads = new Map();
    let fileIntentId = "";
    let fileIntentIndex = null;

    function mount() {
      const current = document.querySelector("#chat-file-list");
      if (current !== mounted || !epoch) {
        mounted = current;
        epoch = newEpoch();
        filterVersion = viewVersion = fileRequest = appliedFileRequest = 0;
        catalogVersions = new Map();
        selectorRequests = new Map();
        appliedSelectors = new Map();
        uploads = new Map();
        fileIntentId = "";
        fileIntentIndex = null;
      }
    }

    function filterChanged() {
      mount();
      filterVersion += 1;
    }

    function viewChanged() {
      mount();
      viewVersion += 1;
      fileIntentId = "";
      fileIntentIndex = null;
    }

    function captureFileSelection(index) {
      mount();
      fileIntentIndex = index;
      return {epoch, viewVersion};
    }

    function applyFileSelection(payload) {
      mount();
      if (!payload || !payload.file_id || payload.file_id !== fileIntentId ||
          payload.stamp.epoch !== epoch || payload.stamp.viewVersion !== viewVersion) return skip(4);
      return [...payload.outputs, epoch + ":" + viewVersion];
    }

    function captureFiles(index) {
      mount();
      fileRequest += 1;
      return { epoch, filterVersion, viewVersion, index,
        catalogVersion: catalogVersions.get(index) || 0, fileRequest };
    }

    function captureSelector(index, indexChanged = false) {
      mount();
      const catalogVersion = (catalogVersions.get(index) || 0) + Number(indexChanged);
      catalogVersions.set(index, catalogVersion);
      const selectorRequest = (selectorRequests.get(index) || 0) + 1;
      selectorRequests.set(index, selectorRequest);
      return { epoch, index, catalogVersion, selectorRequest };
    }

    function uploadChanged(control) {
      viewChanged();
      uploads.set(control, {epoch, viewVersion, control});
    }

    function captureUpload(control) {
      mount();
      if (!uploads.has(control)) uploadChanged(control);
      return uploads.get(control);
    }

    function applyUploadReset(payload) {
      mount();
      if (!payload) return skip(2);
      const stamp = payload.stamp;
      const latest = uploads.get(stamp.control);
      const clear = latest && stamp.epoch === epoch && stamp.viewVersion === latest.viewVersion;
      return [clear ? {__type__: "update", value: null} : skip(1)[0],
        stamp.epoch === epoch && stamp.viewVersion === viewVersion ? {__type__: "update", value: "select"} : skip(1)[0]];
    }

    function applyUploadSelection(payload, currentConversation) {
      mount();
      if (!payload) return skip(1);
      const stamp = payload.stamp;
      return stamp.epoch === epoch && stamp.viewVersion === viewVersion &&
        conversation(payload.conversation) === conversation(currentConversation) ? [payload.ids] : skip(1);
    }

    const skip = (count) => Array.from({ length: count }, () => ({ __type__: "update" }));
    const same = (a, b) => JSON.stringify(a ?? []) === JSON.stringify(b ?? []);
    const conversation = (value) => String(value || "");

    function applyFiles(payload, filter, selected, currentConversation) {
      mount();
      const stamp = payload && payload.stamp;
      if (!stamp || stamp.epoch !== epoch || stamp.fileRequest < appliedFileRequest ||
          stamp.filterVersion !== filterVersion || stamp.viewVersion !== viewVersion ||
          stamp.catalogVersion !== (catalogVersions.get(stamp.index) || 0) ||
          payload.filter !== filter || !same(payload.selected, selected) ||
          conversation(payload.conversation) !== conversation(currentConversation)) {
        return skip(4);
      }
      appliedFileRequest = stamp.fileRequest;
      return payload.outputs;
    }

    function applySelector(payload, selected) {
      mount();
      const stamp = payload && payload.stamp;
      if (!stamp || stamp.epoch !== epoch || stamp.catalogVersion !== catalogVersions.get(stamp.index) ||
          stamp.selectorRequest < (appliedSelectors.get(stamp.index) || 0)) {
        return skip(2);
      }
      appliedSelectors.set(stamp.index, stamp.selectorRequest);
      const update = { ...payload.update };
      if (!same(payload.selected, selected)) {
        update.value = (selected || []).filter(id => payload.available_ids.includes(id));
      } else if (stamp.index === fileIntentIndex && fileIntentId &&
                 payload.available_ids.includes(fileIntentId) &&
                 !same(selected, [fileIntentId]) && same(update.value, selected)) {
        // Both JS calls may capture the pre-flush value. Keep the new card's
        // assignment; this unchanged read must not enqueue that old value again.
        delete update.value;
      }
      return [update, payload.options];
    }

    function input(event) {
      if (event.target.closest && event.target.closest("#chat-file-filter")) filterChanged();
      if (event.target.closest && event.target.closest("#quick-file input[type='file']")) uploadChanged("file");
      if (event.target.closest && event.target.closest("#index-0 input[type='radio']")) viewChanged();
    }

    function click(event) {
      if (!event.target.closest) return;
      const card = event.target.closest("[data-chat-file-id]");
      if (card) {
        viewChanged();
        fileIntentId = card.dataset.chatFileId;
      } else if (event.target.closest("#new-conv-button, #conversation-dropdown [role='option'], #index-0 [role='option'], #index-0 .token-remove")) viewChanged();
    }

    function keydown(event) {
      if (event.key === "Enter" && event.target.closest &&
          event.target.closest("#conversation-dropdown, #index-0")) viewChanged();
    }

    function keypress(event) {
      if (event.key === "Enter" && event.target.closest &&
          event.target.closest("#quick-url, #quick-url-demo")) uploadChanged("url");
    }

    document.addEventListener("input", input, true);
    document.addEventListener("click", click, true);
    document.addEventListener("keydown", keydown, true);
    document.addEventListener("keypress", keypress, true);
    return { captureFiles, captureSelector, applyFiles, applySelector, filterChanged, viewChanged,
      captureUpload, applyUploadReset, applyUploadSelection, uploadChanged,
      captureFileSelection, applyFileSelection };
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { createFileBrowserRefresh };
  if (root.document && !root.maraFileBrowserRefresh) {
    root.maraFileBrowserRefresh = createFileBrowserRefresh(root.document, () => root.crypto.randomUUID());
  }
})(globalThis);

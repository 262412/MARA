
function() {
    const chatInput = document.querySelector("#chat-input textarea");
    const active = document.activeElement;
    if (active !== chatInput && active &&
        (active.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName))) {
        return;
    }
    chatInput.focus();
}

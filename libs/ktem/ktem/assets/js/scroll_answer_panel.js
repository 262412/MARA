
function() {
    setTimeout(() => {
        // Find the correct scrollable element - answer-panel is the scroll container
        var answer_panel = document.querySelector("#answer-panel");
        if (answer_panel) {
            if (answer_panel.scrollHeight > answer_panel.clientHeight) {
                answer_panel.scrollTop = answer_panel.scrollHeight;
            } else {
                var children = answer_panel.children;
                for (var i = 0; i < children.length; i++) {
                    var child = children[i];
                    if (child && child.scrollHeight > child.clientHeight) {
                        child.scrollTop = child.scrollHeight;
                        break;
                    }
                }
            }
        }
    }, 30);
}

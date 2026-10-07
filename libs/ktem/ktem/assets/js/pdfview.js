
function() {
    setTimeout(fullTextSearch(), 100);

    // Get all links and attach click event
    var links = document.getElementsByClassName("pdf-link");
    for (var i = 0; i < links.length; i++) {
        links[i].onclick = openModal;
    }

    // Get all citation links and attach click event
    var links = document.querySelectorAll("a.citation");
    for (var i = 0; i < links.length; i++) {
        links[i].onclick = scrollToCitation;
    }

    var mindmap_el_script = document.querySelector('div.markmap script');

    // render the mindmap if the script tag is present
    if (mindmap_el_script) {
        markmap.autoLoader.renderAll();
    }

    setTimeout(() => {
        var mindmap_el = document.querySelector('svg.markmap');

        var text_nodes = document.querySelectorAll("svg.markmap div");
        for (var i = 0; i < text_nodes.length; i++) {
            text_nodes[i].onclick = fillChatInput;
        }

        if (mindmap_el) {
            function on_svg_export(event) {
                event.preventDefault();
                spawnDocument(mindmap_el, {window: "width=1000,height=1000"});
            }

            var link = document.getElementById("mindmap-toggle");
            if (link) {
                link.onclick = function(event) {
                    event.preventDefault(); // Prevent the default link behavior
                    var div = document.querySelector("div.markmap");
                    if (div) {
                        var currentHeight = div.style.height;
                        if (currentHeight === '400px' || (currentHeight === '')) {
                            div.style.height = '650px';
                        } else {
                            div.style.height = '400px'
                        }
                    }
                };
            }

            var export_link = document.getElementById("mindmap-export");
            if (export_link) {
                export_link.addEventListener('click', on_svg_export);
            }
        }
    }, 250);

    // Auto-scroll answer panel to bottom when content updates
    setTimeout(() => {
        // Find the correct scrollable element - answer-panel is the scroll container
        var answer_panel = document.querySelector("#answer-panel");
        if (answer_panel) {
            // Check if this element itself scrolls
            if (answer_panel.scrollHeight > answer_panel.clientHeight) {
                answer_panel.scrollTo({
                    top: answer_panel.scrollHeight,
                    behavior: 'smooth'
                });
            } else {
                // Otherwise try direct children
                var children = answer_panel.children;
                for (var i = 0; i < children.length; i++) {
                    var child = children[i];
                    if (child && child.scrollHeight > child.clientHeight) {
                        child.scrollTo({
                            top: child.scrollHeight,
                            behavior: 'smooth'
                        });
                        break;
                    }
                }
            }
        }
    }, 30);

    // Setup MutationObserver to auto-scroll on content changes (real-time streaming)
    setTimeout(() => {
        var answer_expand = document.querySelector("#answer-expand");
        if (answer_expand) {
            var observer = new MutationObserver(function(mutations) {
                var answer_panel = document.querySelector("#answer-panel");
                if (answer_panel) {
                    // Scroll immediately without smooth animation
                    // for real-time following
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
            });

            observer.observe(answer_expand, {
                childList: true,
                subtree: true,
                characterData: true
            });
        }
    }, 100);

    // Initialize drag-to-pan for all file previews
    setTimeout(() => {
        function initDragPan(container) {
            if (!container || container.dataset.dragInitialized === 'true') return;

            let isDragging = false;
            let startX = 0, startY = 0;
            let scrollLeft = 0, scrollTop = 0;

            const onMouseDown = (e) => {
                isDragging = true;
                startX = e.pageX - container.offsetLeft;
                startY = e.pageY - container.offsetTop;
                scrollLeft = container.scrollLeft;
                scrollTop = container.scrollTop;
                container.style.cursor = 'grabbing';
                container.style.userSelect = 'none';
                e.preventDefault();
            };

            const onMouseLeave = () => {
                isDragging = false;
                container.style.cursor = 'grab';
                container.style.userSelect = '';
            };

            const onMouseUp = () => {
                isDragging = false;
                container.style.cursor = 'grab';
                container.style.userSelect = '';
            };

            const onMouseMove = (e) => {
                if (!isDragging) return;
                e.preventDefault();
                const x = e.pageX - container.offsetLeft;
                const y = e.pageY - container.offsetTop;
                const walkX = (x - startX) * 1.5;
                const walkY = (y - startY) * 1.5;
                container.scrollLeft = scrollLeft - walkX;
                container.scrollTop = scrollTop - walkY;
            };

            container.addEventListener('mousedown', onMouseDown);
            container.addEventListener('mouseleave', onMouseLeave);
            container.addEventListener('mouseup', onMouseUp);
            container.addEventListener('mousemove', onMouseMove);

            container.dataset.dragInitialized = 'true';
        }

        [
            '.pdf-preview-shell',
            '.docx-preview',
            '.pptx-preview-shell',
            '.xlsx-preview-shell'
        ].forEach(selector => {
            document.querySelectorAll(selector).forEach(el => initDragPan(el));
        });
    }, 150);

    return [links.length]
}


function() {
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
            const walkX = (x - startX) * 1.5; // Scroll speed multiplier
            const walkY = (y - startY) * 1.5;
            container.scrollLeft = scrollLeft - walkX;
            container.scrollTop = scrollTop - walkY;
        };

        // Touch support
        const onTouchStart = (e) => {
            if (e.touches.length !== 1) return;
            isDragging = true;
            const touch = e.touches[0];
            startX = touch.pageX - container.offsetLeft;
            startY = touch.pageY - container.offsetTop;
            scrollLeft = container.scrollLeft;
            scrollTop = container.scrollTop;
            e.preventDefault();
        };

        const onTouchEnd = () => {
            isDragging = false;
        };

        const onTouchMove = (e) => {
            if (!isDragging || e.touches.length !== 1) return;
            e.preventDefault();
            const touch = e.touches[0];
            const x = touch.pageX - container.offsetLeft;
            const y = touch.pageY - container.offsetTop;
            const walkX = (x - startX) * 1.5;
            const walkY = (y - startY) * 1.5;
            container.scrollLeft = scrollLeft - walkX;
            container.scrollTop = scrollTop - walkY;
        };

        // Mouse events
        container.addEventListener('mousedown', onMouseDown);
        container.addEventListener('mouseleave', onMouseLeave);
        container.addEventListener('mouseup', onMouseUp);
        container.addEventListener('mousemove', onMouseMove);

        // Touch events
        container.addEventListener('touchstart', onTouchStart, { passive: false });
        container.addEventListener('touchend', onTouchEnd);
        container.addEventListener('touchmove', onTouchMove, { passive: false });

        container.dataset.dragInitialized = 'true';
    }

    // Initialize on all preview containers
    setTimeout(() => {
        const selectors = [
            '.pdf-preview-shell',
            '.docx-preview',
            '.pptx-preview-shell',
            '.xlsx-preview-shell'
        ];

        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => initDragPan(el));
        });
    }, 100);
}

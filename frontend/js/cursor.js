// ─── Adaptive Cursor Glow ────────────────────────────────────────────────────
// A soft radial glow that follows the cursor and adapts its color
// to match the dominant color of the element underneath it.

(function () {
    // Don't run on touch devices
    if (window.matchMedia('(pointer: coarse)').matches) return;

    // ── Create the glow element ──
    const glow = document.createElement('div');
    glow.id = 'cursor-glow';
    glow.style.cssText = `
        position: fixed;
        top: 0; left: 0;
        width: 320px; height: 320px;
        border-radius: 50%;
        pointer-events: none;
        z-index: 99999;
        transform: translate(-50%, -50%);
        transition: opacity 0.3s ease, background 0.4s ease;
        opacity: 0;
        mix-blend-mode: screen;
        will-change: transform, background;
    `;
    document.body.appendChild(glow);

    // ── Color map: element types / classes → glow color ──
    function getGlowColor(el) {
        if (!el) return null;

        // Walk up the DOM to find a meaningful color hint
        let node = el;
        for (let i = 0; i < 6; i++) {
            if (!node || node === document.body) break;

            const cls = (node.className || '').toString();
            const id  = (node.id || '').toString();
            const tag = (node.tagName || '').toLowerCase();

            // Accent blue — interactive elements, links, buttons
            if (
                tag === 'a' || tag === 'button' ||
                cls.includes('primary-btn') || cls.includes('nav-item') ||
                cls.includes('chat-send-btn') || cls.includes('chat-tab') ||
                cls.includes('pri-btn') || cls.includes('chat-conv-item') ||
                cls.includes('resource-card') || cls.includes('action-link') ||
                cls.includes('pd-stat') || cls.includes('filter-select') ||
                cls.includes('icon-btn') || cls.includes('ghost-btn')
            ) return '34, 211, 238';   // cyan accent

            // Purple — accent purple areas
            if (
                cls.includes('accent-purple') || cls.includes('kpi-purple') ||
                cls.includes('pd-banner') || cls.includes('chat-conv-avatar group') ||
                cls.includes('pri-medium')
            ) return '168, 85, 247';   // purple

            // Red — danger / critical
            if (
                cls.includes('kpi-red') || cls.includes('danger-btn') ||
                cls.includes('pd-logout-btn') || cls.includes('pri-critical') ||
                cls.includes('status breached') || cls.includes('status critical')
            ) return '239, 68, 68';    // red

            // Amber — warning / high priority
            if (
                cls.includes('kpi-orange') || cls.includes('pri-high') ||
                cls.includes('status open') || cls.includes('status pending') ||
                cls.includes('trend-warn')
            ) return '245, 158, 11';   // amber

            // Green — success / resolved
            if (
                cls.includes('kpi-green') || cls.includes('status resolved') ||
                cls.includes('trend-up') || cls.includes('trend-down')
            ) return '16, 185, 129';   // green

            // Blue — info / in-progress
            if (
                cls.includes('kpi-blue') || cls.includes('kpi-cyan') ||
                cls.includes('status prog') || cls.includes('chat-msg-bubble') ||
                cls.includes('pri-medium')
            ) return '59, 130, 246';   // blue

            // Widget / card areas — soft blue
            if (
                cls.includes('widget-v2') || cls.includes('kpi-card') ||
                cls.includes('stat-card') || cls.includes('modal-content') ||
                cls.includes('chat-sidebar') || cls.includes('sidebar')
            ) return '30, 64, 175';    // deep blue

            node = node.parentElement;
        }

        // Default — subtle accent blue
        return '34, 211, 238';
    }

    // ── Smooth position tracking ──
    let mouseX = -500, mouseY = -500;
    let glowX  = -500, glowY  = -500;
    let rafId  = null;
    let currentColor = '34, 211, 238';
    let isVisible = false;

    function lerp(a, b, t) { return a + (b - a) * t; }

    function tick() {
        glowX = lerp(glowX, mouseX, 0.12);
        glowY = lerp(glowY, mouseY, 0.12);

        glow.style.transform = `translate(calc(${glowX}px - 50%), calc(${glowY}px - 50%))`;
        rafId = requestAnimationFrame(tick);
    }

    // ── Mouse events ──
    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;

        if (!isVisible) {
            isVisible = true;
            glow.style.opacity = '1';
            if (!rafId) tick();
        }

        // Sample color from element under cursor
        const el = document.elementFromPoint(e.clientX, e.clientY);
        const color = getGlowColor(el);
        if (color && color !== currentColor) {
            currentColor = color;
            glow.style.background = `radial-gradient(circle, rgba(${color}, 0.12) 0%, rgba(${color}, 0.04) 40%, transparent 70%)`;
        }
    }, { passive: true });

    document.addEventListener('mouseleave', () => {
        isVisible = false;
        glow.style.opacity = '0';
    });

    document.addEventListener('mouseenter', () => {
        isVisible = true;
        glow.style.opacity = '1';
        if (!rafId) tick();
    });

    // Slightly brighter on interactive elements
    document.addEventListener('mouseover', (e) => {
        const el = e.target;
        const tag = (el.tagName || '').toLowerCase();
        const cls = (el.className || '').toString();
        const isInteractive =
            tag === 'a' || tag === 'button' || tag === 'input' ||
            tag === 'select' || tag === 'textarea' ||
            cls.includes('pri-btn') || cls.includes('chat-conv-item') ||
            cls.includes('resource-card') || cls.includes('pd-stat') ||
            cls.includes('nav-item') || cls.includes('chat-user-item');

        glow.style.width  = isInteractive ? '260px' : '320px';
        glow.style.height = isInteractive ? '260px' : '320px';
    }, { passive: true });

    // Initial background
    glow.style.background = `radial-gradient(circle, rgba(34,211,238,0.12) 0%, rgba(34,211,238,0.04) 40%, transparent 70%)`;
})();

// ─── Theme Manager ───────────────────────────────────────────────────────────
(function () {
    const STORAGE_KEY = 'infratick_theme';

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(STORAGE_KEY, theme);

        const btn = document.getElementById('theme-toggle');
        if (!btn) return;
        if (theme === 'light') {
            btn.innerHTML = '<i class="fas fa-moon"></i>';
            btn.title = 'Switch to Dark Mode';
        } else {
            btn.innerHTML = '<i class="fas fa-sun"></i>';
            btn.title = 'Switch to Light Mode';
        }
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        applyTheme(current === 'dark' ? 'light' : 'dark');
    }

    // Apply saved theme immediately (before paint) to avoid flash
    const saved = localStorage.getItem(STORAGE_KEY) || 'dark';
    document.documentElement.setAttribute('data-theme', saved);

    // Wire up button once DOM is ready
    document.addEventListener('DOMContentLoaded', function () {
        applyTheme(saved);
        const btn = document.getElementById('theme-toggle');
        if (btn) btn.addEventListener('click', toggleTheme);
    });

    window.toggleTheme = toggleTheme;
})();

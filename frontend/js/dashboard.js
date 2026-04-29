// Dashboard Logic
document.addEventListener('DOMContentLoaded', () => {
    // Universal View Switching Logic
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.dashboard-view');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            const targetViewId = item.getAttribute('data-view');
            if (!targetViewId) return;

            e.preventDefault();

            // 1. Update active nav item status
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            // 2. Switch views with visual transition
            views.forEach(view => {
                view.classList.remove('active');
                if (view.id === targetViewId) {
                    view.classList.add('active');
                }
            });

            // 3. Dispatch global event for view change (crucial for chart resizing)
            window.dispatchEvent(new CustomEvent('dashboardViewChanged', {
                detail: { viewId: targetViewId }
            }));

            console.log('Orchestrating view transition to:', targetViewId);
        });
    });

    // Mock functionality for "New Ticket" form submission
    const ticketForm = document.querySelector('.modal-body');
    if (ticketForm) {
        ticketForm.addEventListener('submit', (e) => {
            e.preventDefault();
            alert('Ticket initialization sequence started. Sending audit handshake...');
            const modal = document.querySelector('.modal');
            if (modal) modal.style.display = 'none';
        });
    }

    // Role Simulation
    const userRole = localStorage.getItem('userRole') || 'ADMIN';
    const roleBadge = document.querySelector('.user-role');
    if (roleBadge) roleBadge.textContent = userRole;
});

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'flex';
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'none';
}

// Close modal when clicking outside
document.addEventListener('click', function (event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
})

// ─── Toast Notification System ───────────────────────────────────────────────
(function() {
    function getContainer() {
        let c = document.getElementById('toast-container');
        if (!c) {
            c = document.createElement('div');
            c.id = 'toast-container';
            document.body.appendChild(c);
        }
        return c;
    }

    window.showToast = function(message, type = 'info', duration = 3500) {
        const icons = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
        const container = getContainer();
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <i class="fas ${icons[type] || icons.info} toast-icon"></i>
            <span class="toast-msg">${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
        `;
        container.appendChild(toast);
        setTimeout(() => {
            toast.classList.add('toast-out');
            setTimeout(() => toast.remove(), 260);
        }, duration);
        return toast;
    };
})();

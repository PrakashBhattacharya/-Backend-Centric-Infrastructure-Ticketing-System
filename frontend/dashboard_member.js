// Modal Global Functions
function openModal(id) {
    document.getElementById(id).style.display = 'flex';
}

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
}

function openTicketDetail(id) {
    const modal = document.getElementById('ticket-detail-modal');
    if (!modal) return;

    document.getElementById('modal-ticket-id').textContent = id;

    if (id === '#INC-982') {
        document.getElementById('modal-title').textContent = "VPN Connection Timeout";
        document.getElementById('modal-priority').textContent = "High";
        document.getElementById('modal-priority').className = "badge badge-urgent";
        document.getElementById('modal-status').textContent = "In Progress";
        document.getElementById('modal-status').className = "status prog";
        document.getElementById('modal-sla-countdown').textContent = "2h 15m";
        document.getElementById('modal-sla-countdown').style.color = "#f59e0b";
    } else {
        document.getElementById('modal-title').textContent = "Server Downtime Issue";
        document.getElementById('modal-priority').textContent = "Critical";
        document.getElementById('modal-priority').className = "badge badge-critical";
        document.getElementById('modal-status').textContent = "Open";
        document.getElementById('modal-status').className = "status open";
        document.getElementById('modal-sla-countdown').textContent = "Expired";
        document.getElementById('modal-sla-countdown').style.color = "#ef4444";
    }

    modal.style.display = 'flex';
}

document.addEventListener('DOMContentLoaded', () => {
    // Shared chart options
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'bottom',
                labels: { color: '#94a3b8', font: { size: 10 }, usePointStyle: true }
            }
        }
    };

    // 1. Resolution Velocity Chart (Bar)
    const ctxMember = document.getElementById('memberChart').getContext('2d');

    // Vibrant Gradients
    const gradAccent = ctxMember.createLinearGradient(0, 0, 0, 400);
    gradAccent.addColorStop(0, '#22d3ee');
    gradAccent.addColorStop(1, 'rgba(34, 211, 238, 0.05)');

    const gradMuted = ctxMember.createLinearGradient(0, 0, 0, 400);
    gradMuted.addColorStop(0, '#3b82f6');
    gradMuted.addColorStop(1, 'rgba(59, 130, 246, 0.05)');

    const velocityChart = new Chart(ctxMember, {
        type: 'bar',
        data: {
            labels: ['FEB 14', 'FEB 15', 'FEB 16', 'FEB 17', 'FEB 18', 'FEB 19', 'FEB 20'],
            datasets: [
                { label: 'URGENT', data: [0, 0, 0, 0, 0, 0, 0], backgroundColor: gradMuted, borderColor: '#3b82f6', borderWidth: 2, borderRadius: 4, stack: 'S0' },
                { label: 'STANDARD', data: [0, 0, 0, 0, 0, 0, 0], backgroundColor: gradAccent, borderColor: '#22d3ee', borderWidth: 2, borderRadius: 4, stack: 'S0' }
            ]
        },
        options: {
            ...commonOptions,
            scales: {
                y: { stacked: true, grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { color: '#64748b', font: { weight: '600' } } },
                x: { stacked: true, grid: { display: false }, ticks: { color: '#64748b', font: { weight: '600' } } }
            }
        }
    });

    // 2. Priority Breakdown Chart (Donut)
    const ctxPriority = document.getElementById('priorityChart').getContext('2d');
    const priorityChart = new Chart(ctxPriority, {
        type: 'doughnut',
        data: {
            labels: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'],
            datasets: [{
                data: [0, 0, 0, 0],
                backgroundColor: ['#f87171', '#3b82f6', '#1d4ed8', '#1e293b'],
                borderColor: '#0a0c14',
                borderWidth: 4,
                hoverOffset: 20
            }]
        },
        options: { ...commonOptions, cutout: '75%' }
    });

    // 3. Backlog Trend Chart (Line)
    const ctxBacklog = document.getElementById('backlogChart').getContext('2d');
    const backlogChart = new Chart(ctxBacklog, {
        type: 'line',
        data: {
            labels: ['WEEK 1', 'WEEK 2', 'WEEK 3', 'WEEK 4', 'WEEK 5', 'WEEK 6', 'WEEK 7', 'WEEK 8'],
            datasets: [{
                label: 'PENDING VOLUME',
                data: [0, 0, 0, 0, 0, 0, 0, 0],
                borderColor: '#22d3ee',
                backgroundColor: 'rgba(34, 211, 238, 0.03)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointBackgroundColor: '#22d3ee',
                pointBorderColor: '#0a0c14',
                pointBorderWidth: 2,
                pointHoverRadius: 6
            }]
        },
        options: {
            ...commonOptions,
            scales: {
                y: { grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { color: '#64748b' } },
                x: { grid: { display: false }, ticks: { color: '#64748b' } }
            }
        }
    });

    // 4. SLA Status Chart (Donut)
    const ctxSla = document.getElementById('slaDonutChart').getContext('2d');
    const slaChart = new Chart(ctxSla, {
        type: 'doughnut',
        data: {
            labels: ['MET SLA', 'NEAR BREACH', 'BREACHED'],
            datasets: [{
                data: [0, 0, 0],
                backgroundColor: ['#10b981', '#fbbf24', '#f87171'],
                borderColor: '#0a0c14',
                borderWidth: 3
            }]
        },
        options: { ...commonOptions, cutout: '80%' }
    });

    // Navigation and View Logic
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.dashboard-view');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const viewId = item.getAttribute('data-view');

            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            views.forEach(v => {
                v.classList.toggle('active', v.id === viewId);
            });

            // Trigger chart resize after view transition
            if (viewId === 'overview') {
                setTimeout(() => {
                    [velocityChart, priorityChart, backlogChart, slaChart].forEach(chart => chart.resize());
                }, 100);
            }
        });
    });

    console.log("Member Dashboard Ecosystem fully initialized with operational data.");
});

// Close modal when clicking outside
window.onclick = function (event) {
    if (event.target && event.target.classList.contains('modal')) {
        event.target.style.display = "none";
    }
}

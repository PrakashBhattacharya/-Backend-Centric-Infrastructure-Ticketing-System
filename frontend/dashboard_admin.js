document.addEventListener('DOMContentLoaded', function () {

    // ─── STEP 1: TAB SWITCHING ───────────────────────────────────────────────
    var navItems = document.querySelectorAll('.nav-item[data-view]');
    var allViews = document.querySelectorAll('.dashboard-view');
    var chartRegistry = {};

    function showView(viewId) {
        allViews.forEach(function (v) {
            v.style.display = (v.id === viewId) ? 'block' : 'none';
        });
        navItems.forEach(function (n) {
            if (n.getAttribute('data-view') === viewId) {
                n.classList.add('active');
            } else {
                n.classList.remove('active');
            }
        });
        // Defer chart rendering by 50ms so the DOM finishes painting
        setTimeout(function () { renderChartsForView(viewId); }, 50);
    }

    navItems.forEach(function (item) {
        item.addEventListener('click', function (e) {
            e.preventDefault();
            showView(item.getAttribute('data-view'));
        });
    });

    // Show the Overview tab immediately on page load
    showView('overview');


    // ─── STEP 2: CHART RENDERING ─────────────────────────────────────────────
    var chartDefs = {
        'slaComplianceChart': {
            view: 'overview',
            type: 'doughnut',
            data: {
                labels: ['Critical Met', 'High Met', 'Breached'],
                datasets: [{ data: [85, 12, 3], backgroundColor: ['#10b981', '#22d3ee', '#ef4444'], borderWidth: 0, hoverOffset: 4 }]
            },
            options: {
                cutout: '72%', responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#cbd5e1', padding: 16, font: { size: 11 } } },
                    tooltip: { backgroundColor: 'rgba(15,23,42,0.95)', padding: 10 }
                }
            }
        },
        'agingChart': {
            view: 'overview',
            type: 'bar',
            data: {
                labels: ['0-1d', '1-3d', '3-7d', '7d+'],
                datasets: [{ label: 'Tickets', data: [145, 85, 42, 18], backgroundColor: '#3b82f6', borderRadius: 4 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { backgroundColor: 'rgba(15,23,42,0.95)' } },
                scales: {
                    x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' }, beginAtZero: true }
                }
            }
        },
        'backlogTrendChart': {
            view: 'overview',
            type: 'line',
            data: {
                labels: ['Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan'],
                datasets: [{
                    label: 'Open Backlog', data: [420, 390, 450, 480, 410, 342],
                    borderColor: '#8b5cf6', backgroundColor: 'rgba(139,92,246,0.12)',
                    borderWidth: 2, tension: 0.4, fill: true
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { backgroundColor: 'rgba(15,23,42,0.95)' } },
                scales: {
                    x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
                }
            }
        },
        'serviceImpactChart': {
            view: 'operations',
            type: 'bar',
            data: {
                labels: ['Database', 'Network', 'Auth', 'Storage', 'Compute'],
                datasets: [{ label: 'Tickets MTD', data: [124, 98, 75, 54, 32], backgroundColor: ['#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#64748b'], borderRadius: 4 }]
            },
            options: {
                indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { backgroundColor: 'rgba(15,23,42,0.95)' } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                    y: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                }
            }
        },
        'regionLoadChart': {
            view: 'operations',
            type: 'pie',
            data: {
                labels: ['NA-East', 'EU-Central', 'APAC-South', 'NA-West'],
                datasets: [{ data: [45, 25, 20, 10], backgroundColor: ['#3b82f6', '#22d3ee', '#8b5cf6', '#f43f5e'], borderWidth: 0 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#cbd5e1', padding: 16, font: { size: 11 } } },
                    tooltip: { backgroundColor: 'rgba(15,23,42,0.95)' }
                }
            }
        }
    };

    function renderChartsForView(viewId) {
        if (typeof Chart === 'undefined') return;
        Object.keys(chartDefs).forEach(function (id) {
            var def = chartDefs[id];
            if (def.view !== viewId) return;
            if (chartRegistry[id]) return; // already rendered
            var canvas = document.getElementById(id);
            if (!canvas) return;
            try {
                chartRegistry[id] = new Chart(canvas.getContext('2d'), {
                    type: def.type,
                    data: def.data,
                    options: def.options
                });
            } catch (e) {
                console.error('Chart init failed for ' + id + ':', e);
            }
        });
    }


    // ─── STEP 3: ENGINEER PERFORMANCE MATRIX ────────────────────────────────
    (function populateEngineers() {
        var tbody = document.getElementById('engineer-matrix-body');
        if (!tbody) return;
        var engineers = [
            { name: 'Sarah Jenkins', assigned: 14, resolved: 56, mttr: '1.2h', sla: 98, reopens: '0.5%', status: 'excellent' },
            { name: 'Marcus Cole', assigned: 18, resolved: 42, mttr: '1.8h', sla: 94, reopens: '1.2%', status: 'good' },
            { name: 'Elena Rostova', assigned: 22, resolved: 38, mttr: '2.5h', sla: 88, reopens: '3.4%', status: 'warning' },
            { name: 'David Chen', assigned: 9, resolved: 15, mttr: '4.2h', sla: 75, reopens: '5.1%', status: 'critical' },
            { name: 'Aisha Patel', assigned: 11, resolved: 51, mttr: '0.9h', sla: 99, reopens: '0.2%', status: 'excellent' }
        ];
        var statusMap = {
            excellent: '<span class="status resolved">Excellent</span>',
            good: '<span class="status open">Good</span>',
            warning: '<span class="status breached" style="background:rgba(245,158,11,0.1);color:#f59e0b;">Warning</span>',
            critical: '<span class="status breached">Underperforming</span>'
        };
        tbody.innerHTML = engineers.map(function (e) {
            var slaColor = e.sla < 90 ? 'color:#ef4444;font-weight:700;' : '';
            var mttrColor = parseFloat(e.mttr) > 3 ? 'color:#ef4444;font-weight:700;' : '';
            return '<tr>'
                + '<td style="font-weight:600;color:#f8fafc;">' + e.name + '</td>'
                + '<td>' + e.assigned + '</td>'
                + '<td>' + e.resolved + '</td>'
                + '<td style="' + mttrColor + '">' + e.mttr + '</td>'
                + '<td style="' + slaColor + '">' + e.sla + '%</td>'
                + '<td>' + e.reopens + '</td>'
                + '<td>' + (statusMap[e.status] || '') + '</td>'
                + '</tr>';
        }).join('');
    })();


    // ─── STEP 4: AUDIT FEED ──────────────────────────────────────────────────
    (function populateAuditFeed() {
        var feed = document.getElementById('audit-feed');
        if (!feed) return;
        var logs = [
            { icon: 'fa-shield-alt', color: '#3b82f6', text: 'Global IAM Role Policy Updated', time: '2m ago' },
            { icon: 'fa-user-times', color: '#94a3b8', text: 'Offboarded Engineer ID #4092', time: '14m ago' },
            { icon: 'fa-exclamation-triangle', color: '#ef4444', text: 'Login Failure Spike Detected — IP Segment A', time: '1h ago', danger: true },
            { icon: 'fa-database', color: '#f59e0b', text: 'Production DB Snapshot Triggered Manually', time: '3h ago' },
            { icon: 'fa-key', color: '#10b981', text: 'SSH Jump Box Certificate Auto-Rotated', time: '5h ago' },
            { icon: 'fa-lock-open', color: '#8b5cf6', text: 'Sudo Privileges Escalated → Marcus Cole', time: '6h ago' }
        ];
        feed.innerHTML = logs.map(function (l) {
            return '<div class="audit-item">'
                + '<i class="fas ' + l.icon + '" style="color:' + l.color + ';min-width:16px;"></i>'
                + '<span' + (l.danger ? ' style="color:#ef4444;"' : '') + '>' + l.text + '</span>'
                + '<small>' + l.time + '</small>'
                + '</div>';
        }).join('');
    })();

});

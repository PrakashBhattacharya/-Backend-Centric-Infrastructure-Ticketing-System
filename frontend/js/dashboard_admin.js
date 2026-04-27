// ─── Auth Helper ────────────────────────────────────────────────────────────
const API_BASE = window.API_BASE; // Centralized API Base
const AUTH_TOKEN = localStorage.getItem('auth_token');

function authHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${AUTH_TOKEN}`
    };
}

function checkAuth() {
    const role = localStorage.getItem('user_role');
    if (!AUTH_TOKEN || role !== 'admin') {
        window.location.href = 'login.html';
        return false;
    }
    return true;
}

// ─── Global State ───────────────────────────────────────────────────────────
let adminData = null;
let currentTicketId = null;

function openModal(id) {
    document.getElementById(id).style.display = 'flex';
}

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
}

// ─── Global Handlers ────────────────────────────────────────────────────────
window.showAssignModal = async function (ticketId) {
    console.log("showAssignModal triggered for ticket:", ticketId);

    currentTicketId = ticketId;
    document.getElementById('assign-ticket-id').textContent = `#INC-${ticketId}`;

    const select = document.getElementById('engineer-select');
    if (!select) return;

    // Use cached engineers if available, otherwise fetch fresh
    let engineers = (adminData && adminData.engineers && adminData.engineers.length > 0)
        ? adminData.engineers
        : [];

    if (engineers.length === 0) {
        try {
            const res = await fetch(`${API_BASE}/api/dashboard/engineers`, { headers: authHeaders() });
            const data = await res.json();
            if (data.success) engineers = data.engineers;
        } catch (err) {
            console.error("Failed to fetch engineers:", err);
        }
    }

    if (engineers.length === 0) {
        select.innerHTML = '<option value="">No engineers registered</option>';
    } else {
        select.innerHTML = engineers.map(eng => `
            <option value="${eng.id}">${eng.name} (Active: ${eng.assigned})</option>
        `).join('');
    }

    openModal('assign-ticket-modal');
};

window.approveTicket = async function (ticketId) {
    if (!confirm(`Approve resolution for #INC-${ticketId}? This will mark it as Resolved.`)) return;
    try {
        const res = await fetch(`${API_BASE}/api/tickets/${ticketId}/approve`, {
            method: 'PUT',
            headers: authHeaders()
        });
        const data = await res.json();
        if (data.success) {
            await fetchAdminStats();
        } else {
            alert('Error: ' + data.message);
        }
    } catch (err) {
        console.error('Approve error:', err);
    }
};

window.openRejectModal = function (ticketId) {
    currentTicketId = ticketId;
    document.getElementById('reject-ticket-id').textContent = `#INC-${ticketId}`;
    document.getElementById('reject-reason').value = '';
    openModal('reject-ticket-modal');
};

window.confirmReject = async function () {
    const reason = document.getElementById('reject-reason').value.trim();
    if (!reason) {
        alert('Please provide a reason for rejection.');
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/api/tickets/${currentTicketId}/reject`, {
            method: 'PUT',
            headers: authHeaders(),
            body: JSON.stringify({ reason })
        });
        const data = await res.json();
        if (data.success) {
            closeModal('reject-ticket-modal');
            await fetchAdminStats();
        } else {
            alert('Error: ' + data.message);
        }
    } catch (err) {
        console.error('Reject error:', err);
    }
};

window.assignTicket = async function (ticketId, engineerId) {    console.log("assignTicket API call for:", ticketId, "to:", engineerId);
    try {
        const res = await fetch(`${API_BASE}/api/tickets/${ticketId}/assign`, {
            method: 'PUT',
            headers: authHeaders(),
            body: JSON.stringify({ engineer_id: engineerId })
        });
        const data = await res.json();
        if (data.success) {
            closeModal('assign-ticket-modal');
            alert('Ticket assigned successfully!');
            await fetchAdminStats(); // Refresh UI
        } else {
            alert("Error: " + data.message);
        }
    } catch (err) {
        console.error("Assignment network error:", err);
        alert("Failed to connect to backend server.");
    }
};

// ─── Main Init ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    if (!checkAuth()) return;

    // Set user info
    const userName = localStorage.getItem('user_name') || 'Admin';
    const userNameEl = document.querySelector('.user-name');
    const avatarEl = document.querySelector('.profile-avatar');
    if (userNameEl) userNameEl.textContent = userName;
    if (avatarEl) avatarEl.textContent = userName.charAt(0).toUpperCase();

    // Fetch snapshot
    await fetchAdminStats();

    // View Switching
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.dashboard-view');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const viewId = item.getAttribute('data-view');
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            views.forEach(v => v.classList.toggle('active', v.id === viewId));
        });
    });

    // EVENT DELEGATION for Assign Buttons
    const ticketBody = document.getElementById('all-tickets-body');
    if (ticketBody) {
        ticketBody.addEventListener('click', (e) => {
            const btn = e.target.closest('.assign-btn');
            if (btn) {
                // Event delegation is enough, we can remove the onclick from the HTML generator if we want,
                // but for now we'll just handle it here if it wasn't already handled.
                // Actually, the button has onclick="window.showAssignModal(...)".
                // Delegation here is redundant if onclick is present.
                // Let's rely on the button attribute.
                const ticketId = btn.getAttribute('data-id');
                window.showAssignModal(ticketId);
            }
        });
    }

    // Modal Confirmation Button
    const confirmBtn = document.getElementById('confirm-assign-btn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
            const engineerId = document.getElementById('engineer-select').value;
            if (currentTicketId && engineerId) {
                window.assignTicket(currentTicketId, engineerId);
            }
        });
    }

    // Global Search
    const searchInput = document.getElementById('global-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            if (!adminData) return;

            // Filter Tickets
            const filteredTickets = adminData.all_tickets.filter(t => 
                (t.subject || '').toLowerCase().includes(query) || 
                (t.id || '').toString().includes(query) ||
                (t.creator_name || '').toLowerCase().includes(query)
            );
            populateAllTicketsTable(filteredTickets);

            // Filter Engineers
            const filteredEngineers = adminData.engineers.filter(eng => 
                (eng.name || '').toLowerCase().includes(query) || 
                (eng.id || '').toString().includes(query)
            );
            populateEngineerMatrix(filteredEngineers);

            // Filter Audit Logs
            const filteredLogs = adminData.auditLogs.filter(log => 
                (log.text || '').toLowerCase().includes(query)
            );
            populateAuditFeed(filteredLogs);
        });
    }
});

async function fetchAdminStats() {
    try {
        console.log("Fetching admin stats for governance dashboard...");
        const res = await fetch(`${API_BASE}/api/dashboard/admin/overview`, { 
            headers: authHeaders(),
            cache: 'no-store' // Ensure fresh data
        });
        
        if (!res.ok) {
            throw new Error(`Cloud API returned ${res.status}`);
        }

        const data = await res.json();
        if (data.success) {
            adminData = data;
            
            // Execute all population functions safely
            try { updateKPIs(data); } catch (e) { console.error("KPI Update Error:", e); }
            try { populateEngineerMatrix(data.engineers || []); } catch (e) { console.error("Engineer Matrix Error:", e); }
            try { populateAuditFeed(data.auditLogs || []); } catch (e) { console.error("Audit Feed Error:", e); }
            try { populateAllTicketsTable(data.all_tickets || []); } catch (e) { console.error("Tickets Table Error:", e); }
            try { initCharts(data); } catch (e) { console.error("Chart Initialization Error:", e); }
            
        } else {
            console.error("Governance API error:", data.message);
        }
    } catch (err) {
        console.error("Critical Failure in Admin Dashboard fetch:", err);
    }
}

function updateKPIs(data) {
    const kpis = document.querySelectorAll('.kpi-value');
    if (kpis.length >= 6) {
        kpis[0].textContent = data.total_open || 0;
        kpis[1].textContent = data.breaches_today || 0;
        kpis[2].textContent = data.escalated || 0;
        kpis[3].textContent = data.mttr || '0.0h';
        kpis[4].textContent = (data.reopen_rate || 0) + '%';
        kpis[5].textContent = data.avg_aging || '0.0d';
    }

    // Show pending approval badge on the Tools nav item
    const pending = data.pending_approval || 0;
    const toolsNav = document.querySelector('.nav-item[data-view="tools"]');
    if (toolsNav) {
        let badge = toolsNav.querySelector('.pending-badge');
        if (pending > 0) {
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'pending-badge';
                badge.style.cssText = 'margin-left:auto; background:#f59e0b; color:#0f172a; font-size:10px; font-weight:800; padding:2px 7px; border-radius:999px;';
                toolsNav.appendChild(badge);
            }
            badge.textContent = pending;
        } else if (badge) {
            badge.remove();
        }
    }
}

function populateEngineerMatrix(engineers) {
    const tbody = document.getElementById('engineer-matrix-body');
    if (!tbody) return;

    if (!Array.isArray(engineers) || engineers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:30px; color:var(--text-secondary);">No engineers registered yet.</td></tr>';
        return;
    }

    tbody.innerHTML = engineers.map(eng => {
        const status = (eng.status || 'unknown').toLowerCase();
        const statusClass = status === 'excellent' ? 'resolved' : (status === 'warning' ? 'open' : status === 'critical' ? 'critical' : '');
        return `
            <tr>
                <td>
                    <div style="display:flex; align-items:center; gap:10px;">
                        <div class="profile-avatar" style="width:28px; height:28px; font-size:12px;">${eng.name ? eng.name.charAt(0) : '?'}</div>
                        <span>ID: ${eng.id} — ${eng.name || 'Unknown'}</span>
                    </div>
                </td>
                <td>${eng.assigned || 0}</td>
                <td>${eng.resolved || 0}</td>
                <td>${eng.mttr || '-'}</td>
                <td>${eng.sla || 0}%</td>
                <td>${eng.reopens || '0%'}</td>
                <td><span class="status ${statusClass}">${status.toUpperCase()}</span></td>
            </tr>
        `;
    }).join('');
}

function populateAuditFeed(logs) {
    const feed = document.getElementById('audit-feed');
    if (!feed) return;

    if (!Array.isArray(logs) || logs.length === 0) {
        feed.innerHTML = '<div style="color:var(--text-secondary); padding:20px; text-align:center;">No recent activity.</div>';
        return;
    }

    feed.innerHTML = logs.map(log => `
        <div class="density-item" ${log.danger ? 'style="border-color: rgba(239,68,68,0.2);"' : ''}>
            <div class="density-icon-box" style="background:${log.color || '#3b82f6'}22; color:${log.color || '#3b82f6'};">
                <i class="fas ${log.icon || 'fa-info-circle'}"></i>
            </div>
            <div class="density-content">
                <div class="density-label">${log.text || 'Audit Event'}</div>
                <div class="density-sub">${log.sub ? log.sub + ' · ' : ''}${log.time || '--:--'}</div>
            </div>
        </div>
    `).join('');
}

function populateAllTicketsTable(tickets) {
    const tbody = document.getElementById('all-tickets-body');
    if (!tbody) return;

    if (!Array.isArray(tickets) || tickets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:30px; color:var(--text-secondary);">No tickets found.</td></tr>';
        return;
    }

    tbody.innerHTML = tickets.map(t => {
        const priorityClass = t.priority === 'Critical' ? 'critical' : (t.priority === 'High' ? 'high' : (t.priority === 'Medium' ? 'med' : 'low'));
        const statusClass = t.status === 'Resolved' ? 'resolved' : (t.status === 'In Progress' ? 'prog' : t.status === 'Pending Approval' ? 'pending' : 'open');
        const isAssigned = t.assigned_to !== null && t.assigned_to !== undefined;
        const isPending = t.status === 'Pending Approval';

        return `
            <tr style="cursor:pointer;${isPending ? 'background:rgba(245,158,11,0.04);' : ''}" onclick="openTicketDetail(${t.id})">
                <td>#INC-${t.id}</td>
                <td>${t.subject || 'No Subject'}${isPending ? ' <span style="font-size:10px; background:rgba(245,158,11,0.15); color:#f59e0b; padding:2px 6px; border-radius:4px; font-weight:700; margin-left:6px;">NEEDS REVIEW</span>' : ''}</td>
                <td><span class="priority ${priorityClass}">${t.priority || 'Low'}</span></td>
                <td><span class="status ${statusClass}">${t.status || 'Open'}</span></td>
                <td>${t.creator_name || '-'}</td>
                <td>${t.assignee_name || '<span style="color:#f59e0b;">Unassigned</span>'}</td>
                <td>
                    <div class="action-group">
                        ${isPending ? `
                            <button class="primary-btn sm" style="background:#10b981; padding:4px 10px; font-size:11px;" onclick="event.stopPropagation(); approveTicket(${t.id})">
                                <i class="fas fa-check"></i> Approve
                            </button>
                            <button class="primary-btn sm" style="background:#ef4444; padding:4px 10px; font-size:11px;" onclick="event.stopPropagation(); openRejectModal(${t.id})">
                                <i class="fas fa-times"></i> Reject
                            </button>
                        ` : `
                            <button class="primary-btn sm assign-btn" data-id="${t.id}" style="padding:4px 12px; font-size:11px;"
                                onclick="event.stopPropagation(); window.showAssignModal(${t.id})">
                                ${isAssigned ? 'Reassign' : 'Assign'}
                            </button>
                        `}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

async function openTicketDetail(ticketId) {
    const modal = document.getElementById('ticket-detail-modal');
    if (!modal) return;

    try {
        const res = await fetch(`${API_BASE}/api/tickets/${ticketId}`, { headers: authHeaders() });
        const data = await res.json();
        if (!data.success) return;

        const t = data.ticket;
        if (!t) return;

        document.getElementById('modal-ticket-id').textContent = `#INC-${t.id}`;
        document.getElementById('modal-title').textContent = t.subject || 'No Subject';
        document.getElementById('modal-desc').textContent = t.description || 'No description provided.';
        document.getElementById('modal-creator').textContent = t.creator_name || 'System';
        document.getElementById('modal-assignee').textContent = t.assignee_name || 'Unassigned';

        const priorityEl = document.getElementById('modal-priority');
        priorityEl.textContent = t.priority || 'Low';
        priorityEl.className = 'badge ' + (t.priority === 'Critical' ? 'badge-critical' : 'badge-urgent');

        const statusEl = document.getElementById('modal-status');
        statusEl.textContent = t.status || 'Open';
        const statusClass = t.status === 'Resolved' ? 'resolved' : (t.status === 'In Progress' ? 'prog' : 'open');
        statusEl.className = 'status ' + statusClass;

        const slaEl = document.getElementById('modal-sla-countdown');
        if (t.sla_breached) {
            slaEl.textContent = 'BREACHED';
            slaEl.style.color = '#ef4444';
        } else if (t.status === 'Resolved' || t.status === 'Closed') {
            slaEl.textContent = 'RESOLVED';
            slaEl.style.color = '#10b981';
        } else {
            const now = new Date();
            const slaDeadline = parseDate(t.sla_deadline);
            if (now > slaDeadline) {
                slaEl.textContent = 'BREACHED';
                slaEl.style.color = '#ef4444';
            } else {
                const diff = slaDeadline - now;
                const hours = Math.floor(diff / 3600000);
                const mins = Math.floor((diff % 3600000) / 60000);
                slaEl.textContent = `${hours}h ${mins}m remaining`;
                slaEl.style.color = hours < 2 ? '#f59e0b' : '#10b981';
            }
        }

        document.getElementById('modal-created').textContent = t.created_at ? parseDate(t.created_at).toLocaleDateString() : '-';

        // Comments
        const commentsDiv = document.getElementById('modal-comments');
        if (Array.isArray(data.comments) && data.comments.length > 0) {
            commentsDiv.innerHTML = data.comments.map(c => `
                <div class="timeline-item">
                    <div class="timeline-point"></div>
                    <div class="timeline-info">${c.author_name} | ${parseDate(c.created_at).toLocaleString()}</div>
                    <div class="timeline-action">${c.text}</div>
                </div>
            `).join('');
        } else {
            commentsDiv.innerHTML = '<div style="color:var(--text-secondary); font-size:12px;">No activity logged yet.</div>';
        }

        openModal('ticket-detail-modal');
    } catch (err) {
        console.error('Error fetching ticket detail:', err);
    }
}

function initCharts(data) {
    if (typeof Chart === 'undefined') {
        console.error("Critical: Chart.js library is not loaded.");
        return;
    }
    const chartFont = {
        family: "'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        size: 10,
        weight: '600'
    };

    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 10, bottom: 10, left: 10, right: 10 } },
        plugins: { 
            legend: { 
                position: 'bottom', 
                labels: { 
                    color: '#94a3b8', 
                    font: chartFont, 
                    usePointStyle: true,
                    pointStyle: 'circle',
                    padding: 15
                } 
            },
            tooltip: {
                backgroundColor: 'rgba(10, 14, 28, 0.98)',
                titleFont: { family: chartFont.family, size: 12, weight: '700' },
                bodyFont: { family: chartFont.family, size: 11 },
                titleColor: '#f1f5f9',
                bodyColor: '#94a3b8',
                borderColor: 'rgba(59, 130, 246, 0.2)',
                borderWidth: 1,
                padding: 12,
                cornerRadius: 10
            }
        },
        animation: {
            duration: 2000,
            easing: 'easeOutQuart'
        }
    };

    const chartIds = ['slaComplianceChart', 'agingChart', 'serviceImpactChart', 'regionLoadChart', 'backlogTrendChart'];
    chartIds.forEach(id => {
        const existingChart = Chart.getChart(id);
        if (existingChart) existingChart.destroy();
    });

    // 1. SLA Compliance Chart (Donut) — Enhanced with real data & gradients
    const ctxSla = document.getElementById('slaComplianceChart');
    if (ctxSla) {
        new Chart(ctxSla, {
            type: 'doughnut',
            data: {
                labels: ['COMPLIANT', 'NEAR BREACH', 'BREACHED'],
                datasets: [{
                    data: data.slaComplianceData || [0, 0, 0],
                    backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
                    borderColor: '#0f172a',
                    borderWidth: 5,
                    hoverOffset: 15
                }]
            },
            options: { 
                ...commonOptions, 
                cutout: '80%',
                plugins: {
                    ...commonOptions.plugins,
                    legend: { ...commonOptions.plugins.legend, position: 'bottom' }
                }
            }
        });
    }

    // 2. Backlog Aging Chart (Bar) — Upgrade with gradients
    const ctxAging = document.getElementById('agingChart');
    if (ctxAging) {
        const ctx = ctxAging.getContext('2d');
        const grad = ctx.createLinearGradient(0, 0, 0, 300);
        grad.addColorStop(0, '#3b82f6'); grad.addColorStop(1, 'rgba(59, 130, 246, 0.1)');

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['< 24h', '1-3 Days', '3-7 Days', '7+ Days'],
                datasets: [{
                    label: 'Tickets',
                    data: data.agingData || [0, 0, 0, 0],
                    backgroundColor: grad,
                    borderColor: '#3b82f6',
                    borderWidth: 1,
                    borderRadius: 8
                }]
            },
            options: {
                ...commonOptions,
                plugins: { ...commonOptions.plugins, legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false }, ticks: { color: '#64748b' } },
                    x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { weight: '600' } } }
                }
            }
        });
    }

    // 3. Service Impact Distribution (Radar) — Premium sleek look
    const ctxService = document.getElementById('serviceImpactChart');
    if (ctxService) {
        new Chart(ctxService, {
            type: 'radar',
            data: {
                labels: ['Database', 'Networking', 'Compute', 'Security', 'Storage'],
                datasets: [{
                    label: 'Open incidents',
                    data: data.serviceImpactData || [0, 0, 0, 0, 0],
                    borderColor: '#22d3ee',
                    backgroundColor: 'rgba(34, 211, 238, 0.15)',
                    borderWidth: 3,
                    pointBackgroundColor: '#22d3ee',
                    pointBorderColor: '#0f172a',
                    pointHoverRadius: 6
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    r: { 
                        grid: { color: 'rgba(255,255,255,0.05)' }, 
                        angleLines: { color: 'rgba(255,255,255,0.05)' },
                        pointLabels: { color: '#94a3b8', font: { size: 10, weight: '600' } }, 
                        ticks: { display: false } 
                    }
                }
            }
        });
    }

    // 4. Backlog Growth (Line) — Real Trend Data
    const ctxBacklog = document.getElementById('backlogTrendChart');
    if (ctxBacklog) {
        const ctx = ctxBacklog.getContext('2d');
        const gradFill = ctx.createLinearGradient(0, 0, 0, 300);
        gradFill.addColorStop(0, 'rgba(139, 92, 246, 0.2)');
        gradFill.addColorStop(1, 'rgba(139, 92, 246, 0)');

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['6d ago', '5d ago', '4d ago', '3d ago', '2d ago', 'Yest', 'Today'],
                datasets: [{
                    label: 'New Incidents',
                    data: data.backlogTrendData || [0, 0, 0, 0, 0, 0, 0],
                    borderColor: '#8b5cf6',
                    tension: 0.45,
                    fill: true,
                    backgroundColor: gradFill,
                    borderWidth: 3,
                    pointRadius: 4,
                    pointHoverRadius: 8
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#64748b' } },
                    x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 9 } } }
                }
            }
        });
    }

    // 5. Regional Load Chart (Doughnut) — Mapped Real Data
    const ctxRegion = document.getElementById('regionLoadChart');
    if (ctxRegion) {
        new Chart(ctxRegion, {
            type: 'doughnut',
            data: {
                labels: ['Americas (Prod)', 'Europe (Stage)', 'Asia-Pac (Dev)', 'Global (Edge)'],
                datasets: [{
                    data: data.regionLoadData || [0, 0, 0, 0],
                    backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#94a3b8'],
                    borderColor: '#0f172a',
                    borderWidth: 3
                }]
            },
            options: { 
                ...commonOptions, 
                cutout: '72%', 
                plugins: { 
                    ...commonOptions.plugins, 
                    legend: { 
                        position: 'right', 
                        labels: { boxWidth: 12, color: '#94a3b8', font: { size: 10 } } 
                    } 
                } 
            }
        });
    }
}

function logout() {
    localStorage.clear();
    window.location.href = 'login.html';
}

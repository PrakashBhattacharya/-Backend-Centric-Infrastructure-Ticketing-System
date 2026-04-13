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
window.showAssignModal = function (ticketId) {
    console.log("showAssignModal triggered for ticket:", ticketId);
    if (!adminData || !adminData.engineers) {
        alert("Engineer data not loaded. Please refresh.");
        return;
    }

    currentTicketId = ticketId;
    document.getElementById('assign-ticket-id').textContent = `#INC-${ticketId}`;
    
    // Populate dropdown
    const select = document.getElementById('engineer-select');
    if (select) {
        select.innerHTML = adminData.engineers.map(eng => `
            <option value="${eng.id}">${eng.name} (Assigned: ${eng.assigned})</option>
        `).join('');
    }

    openModal('assign-ticket-modal');
};

window.assignTicket = async function (ticketId, engineerId) {
    console.log("assignTicket API call for:", ticketId, "to:", engineerId);
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
        console.log("Fetching admin stats...");
        const res = await fetch(`${API_BASE}/api/dashboard/admin/overview`, { headers: authHeaders() });
        const data = await res.json();
        if (data.success) {
            adminData = data;
            updateKPIs(data);
            populateEngineerMatrix(data.engineers);
            populateAuditFeed(data.auditLogs);
            populateAllTicketsTable(data.all_tickets);
            initCharts(data);
        } else {
            console.error("API error:", data.message);
        }
    } catch (err) {
        console.error("Failed to fetch admin stats:", err);
    }
}

function updateKPIs(data) {
    const kpis = document.querySelectorAll('.kpi-value');
    if (kpis.length >= 6) {
        kpis[0].textContent = data.total_open || 0;
        kpis[1].textContent = data.breaches_today || 0;
        kpis[2].textContent = data.escalated || 0;
        kpis[3].textContent = data.total_resolved || 0;
        kpis[4].textContent = data.total_all || 0;
        kpis[5].textContent = (data.reopen_rate || 0) + '%';
    }
}

function populateEngineerMatrix(engineers) {
    const tbody = document.getElementById('engineer-matrix-body');
    if (!tbody) return;

    if (!engineers || engineers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:30px; color:var(--text-secondary);">No engineers registered yet.</td></tr>';
        return;
    }

    tbody.innerHTML = engineers.map(eng => `
        <tr>
            <td>
                <div style="display:flex; align-items:center; gap:10px;">
                    <div class="profile-avatar" style="width:28px; height:28px; font-size:12px;">${eng.name ? eng.name.charAt(0) : '?'}</div>
                    <span>ID: ${eng.id} — ${eng.name}</span>
                </div>
            </td>
            <td>${eng.assigned}</td>
            <td>${eng.resolved}</td>
            <td>${eng.mttr}</td>
            <td>${eng.sla}%</td>
            <td>${eng.reopens}</td>
            <td><span class="status ${eng.status === 'excellent' ? 'resolved' : (eng.status === 'warning' ? 'open' : '')}">${eng.status.toUpperCase()}</span></td>
        </tr>
    `).join('');
}

function populateAuditFeed(logs) {
    const feed = document.getElementById('audit-feed');
    if (!feed) return;

    if (!logs || logs.length === 0) {
        feed.innerHTML = '<div style="color:var(--text-secondary); padding:20px; text-align:center;">No recent activity.</div>';
        return;
    }

    feed.innerHTML = logs.map(log => `
        <div class="density-item" ${log.danger ? 'style="border-color: rgba(239,68,68,0.2);"' : ''}>
            <div class="density-icon-box" style="background:${log.color}22; color:${log.color};">
                <i class="fas ${log.icon}"></i>
            </div>
            <div class="density-content">
                <div class="density-label">${log.text}</div>
                <div class="density-sub">${log.time}</div>
            </div>
        </div>
    `).join('');
}

function populateAllTicketsTable(tickets) {
    const tbody = document.getElementById('all-tickets-body');
    if (!tbody) return;

    if (!tickets || tickets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:30px; color:var(--text-secondary);">No tickets found.</td></tr>';
        return;
    }

    tbody.innerHTML = tickets.map(t => {
        const priorityClass = t.priority === 'Critical' ? 'critical' : (t.priority === 'High' ? 'high' : (t.priority === 'Medium' ? 'med' : 'low'));
        const statusClass = t.status === 'Resolved' ? 'resolved' : (t.status === 'In Progress' ? 'prog' : 'open');
        const isAssigned = t.assigned_to !== null && t.assigned_to !== undefined;
        
        return `
            <tr style="cursor:pointer;" onclick="openTicketDetail(${t.id})">
                <td>#INC-${t.id}</td>
                <td>${t.subject}</td>
                <td><span class="priority ${priorityClass}">${t.priority}</span></td>
                <td><span class="status ${statusClass}">${t.status}</span></td>
                <td>${t.creator_name || '-'}</td>
                <td>${t.assignee_name || '<span style="color:#f59e0b;">Unassigned</span>'}</td>
                <td>
                    <button class="primary-btn sm assign-btn" data-id="${t.id}" style="padding:4px 12px; font-size:11px;" 
                        onclick="event.stopPropagation(); window.showAssignModal(${t.id})">
                        ${isAssigned ? 'Reassign' : 'Assign'}
                    </button>
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
        document.getElementById('modal-ticket-id').textContent = `#INC-${t.id}`;
        document.getElementById('modal-title').textContent = t.subject;
        document.getElementById('modal-desc').textContent = t.description || 'No description provided.';
        document.getElementById('modal-creator').textContent = t.creator_name || 'System';
        document.getElementById('modal-assignee').textContent = t.assignee_name || 'Unassigned';

        const priorityEl = document.getElementById('modal-priority');
        priorityEl.textContent = t.priority;
        priorityEl.className = 'badge ' + (t.priority === 'Critical' ? 'badge-critical' : 'badge-urgent');

        const statusEl = document.getElementById('modal-status');
        statusEl.textContent = t.status;
        const statusClass = t.status === 'Resolved' ? 'resolved' : (t.status === 'In Progress' ? 'prog' : 'open');
        statusEl.className = 'status ' + statusClass;

        const slaEl = document.getElementById('modal-sla-countdown');
        const now = new Date();
        const slaDeadline = parseDate(t.sla_deadline);
        if (t.sla_breached === true) {
            slaEl.textContent = 'Breached';
            slaEl.style.color = '#ef4444';
        } else if (t.status === 'Resolved' || t.status === 'Closed') {
            slaEl.textContent = 'Resolved';
            slaEl.style.color = '#10b981';
        } else if (now > slaDeadline) {
            slaEl.textContent = 'Breached';
            slaEl.style.color = '#ef4444';
        } else {
            const diff = slaDeadline - now;
            const hours = Math.floor(diff / 3600000);
            const mins = Math.floor((diff % 3600000) / 60000);
            slaEl.textContent = `${hours}h ${mins}m remaining`;
            slaEl.style.color = hours < 2 ? '#f59e0b' : '#10b981';
        }

        document.getElementById('modal-created').textContent = parseDate(t.created_at).toLocaleDateString();

        // Comments
        const commentsDiv = document.getElementById('modal-comments');
        if (data.comments && data.comments.length > 0) {
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
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 }, usePointStyle: true } } }
    };

    const chartIds = ['slaComplianceChart', 'agingChart', 'serviceImpactChart', 'regionLoadChart', 'backlogTrendChart'];
    chartIds.forEach(id => {
        const existingChart = Chart.getChart(id);
        if (existingChart) existingChart.destroy();
    });

    // 1. SLA Compliance Chart (Donut)
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
                    borderWidth: 3
                }]
            },
            options: { ...commonOptions, cutout: '75%' }
        });
    }

    // 2. Backlog Aging Chart (Bar)
    const ctxAging = document.getElementById('agingChart');
    if (ctxAging) {
        new Chart(ctxAging, {
            type: 'bar',
            data: {
                labels: ['< 24h', '1-3 Days', '3-7 Days', '7+ Days'],
                datasets: [{
                    label: 'Tickets',
                    data: data.agingData || [0, 0, 0, 0],
                    backgroundColor: ['#22d3ee', '#3b82f6', '#f59e0b', '#ef4444'],
                    borderRadius: 6
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { color: '#64748b' } },
                    x: { grid: { display: false }, ticks: { color: '#64748b' } }
                }
            }
        });
    }

    // 3. Service Impact Distribution (Radar)
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
                    borderWidth: 2
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    r: { grid: { color: 'rgba(255,255,255,0.05)' }, pointLabels: { color: '#94a3b8' }, ticks: { display: false } }
                }
            }
        });
    }

    // 4. Backlog Growth (Line)
    const ctxBacklog = document.getElementById('backlogTrendChart');
    if (ctxBacklog) {
        new Chart(ctxBacklog, {
            type: 'line',
            data: {
                labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Now'],
                datasets: [{
                    label: 'Backlog',
                    data: data.backlogTrendData || [0, 0, 0, 0, 0, 0],
                    borderColor: '#8b5cf6',
                    tension: 0.4,
                    fill: true,
                    backgroundColor: 'rgba(139, 92, 246, 0.05)',
                    borderWidth: 3
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.02)' } },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    // 5. Regional Load Chart (Doughnut)
    const ctxRegion = document.getElementById('regionLoadChart');
    if (ctxRegion) {
        new Chart(ctxRegion, {
            type: 'doughnut',
            data: {
                labels: ['US-East', 'EU-West', 'AP-South', 'Other'],
                datasets: [{
                    data: data.regionLoadData || [0, 0, 0, 0],
                    backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'],
                    borderColor: '#0f172a',
                    borderWidth: 2
                }]
            },
            options: { ...commonOptions, cutout: '70%', plugins: { ...commonOptions.plugins, legend: { position: 'right', labels: { boxWidth: 10, color: '#94a3b8' } } } }
        });
    }
}

function logout() {
    localStorage.clear();
    window.location.href = 'login.html';
}

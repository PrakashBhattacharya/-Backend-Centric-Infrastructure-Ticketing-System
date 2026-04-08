// ─── Auth Helper ────────────────────────────────────────────────────────────
const API_BASE = window.API_BASE;
const AUTH_TOKEN = localStorage.getItem('auth_token');

function authHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${AUTH_TOKEN}`
    };
}

function checkAuth() {
    const role = localStorage.getItem('user_role');
    if (!AUTH_TOKEN || role !== 'engineer') {
        window.location.href = 'login.html';
        return false;
    }
    return true;
}

// ─── Global State ───────────────────────────────────────────────────────────
let adminData = null; // Reusing naming for consistency across dashboards if needed, but let's use engineerStore
let engineerStore = {
    queue: [],
    resolved: []
};

const KNOWLEDGE_BASE_DATA = {
    'Edge Console': {
        subtitle: 'Secure Shell Connectivity Guide',
        content: `
            <p>Access protocols for multi-tenant edge nodes:</p>
            <ul style="margin-left: 20px; margin-top: 10px;">
                <li><strong>Endpoint:</strong> <code>ssh.infra.tick.net</code></li>
                <li><strong>Jump Host:</strong> All connections must route via the Bastion server (Region-specific).</li>
                <li><strong>Identity:</strong> Use your Provisioned PKI Certificate (RSA-4096).</li>
                <li><strong>Policy:</strong> Session logging is enforced for compliance auditing.</li>
            </ul>
        `
    },
    'API Docs': {
        subtitle: 'Internal Ticketing API Reference',
        content: `
            <p>Programmatic incident management:</p>
            <ul style="margin-left: 20px; margin-top: 10px;">
                <li><strong>Base URL:</strong> <code>/api/v2/infrastructure/*</code></li>
                <li><strong>Auth:</strong> JWT Bearer token required in Authorization header.</li>
                <li><strong>Key Endpoints:</strong>
                    <br><code>PUT /status</code> - Bulk status updates
                    <br><code>POST /escalate</code> - Tier-3 elevation
                </li>
            </ul>
        `
    },
    'Debug Suite': {
        subtitle: 'Diagnostic Tooling Ecosystem',
        content: `
            <p>Critical diagnostic utilities available on all nodes:</p>
            <ul style="margin-left: 20px; margin-top: 10px;">
                <li><strong>LogAnalyzer:</strong> <code>infra-logs --follow --id [INC-ID]</code></li>
                <li><strong>NetTracer:</strong> Visualizes cluster latency and packet loss.</li>
                <li><strong>HealthCheck:</strong> Runs automated stress tests against specified VPC segments.</li>
            </ul>
        `
    }
};

window.showKnowledgeDetail = function(title) {
    const data = KNOWLEDGE_BASE_DATA[title];
    if (!data) return;
    
    document.getElementById('knowledge-title').textContent = title;
    document.getElementById('knowledge-subtitle').textContent = data.subtitle;
    document.getElementById('knowledge-body').innerHTML = data.content;
    openModal('knowledge-detail-modal');
};

function openModal(id) {
    document.getElementById(id).style.display = 'flex';
}

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
}

// ─── Main Init ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    if (!checkAuth()) return;

    // Set user info
    const userName = localStorage.getItem('user_name') || 'Engineer';
    const userNameEl = document.querySelector('.user-name');
    const avatarEl = document.querySelector('.profile-avatar');
    if (userNameEl) userNameEl.textContent = userName;
    if (avatarEl) avatarEl.textContent = userName.charAt(0).toUpperCase();

    // Fetch Initial Data
    await refreshData();

    // Navigation View Logic
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
        });
    });

    // Global Search Logic
    const searchInput = document.getElementById('global-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            
            const filteredQueue = engineerStore.queue.filter(t => 
                (t.subject || '').toLowerCase().includes(query) || 
                (t.id || '').toString().includes(query)
            );
            populateQueue(filteredQueue);

            const filteredResolved = engineerStore.resolved.filter(t => 
                (t.subject || '').toLowerCase().includes(query) || 
                (t.id || '').toString().includes(query)
            );
            populateResolvedTable(filteredResolved);
        });
    }
});

async function refreshData() {
    try {
        const res = await fetch(`${API_BASE}/api/dashboard/engineer`, { headers: authHeaders() });
        const data = await res.json();

        if (data.success) {
            engineerStore.queue = data.queue || [];
            engineerStore.resolved = data.resolved_list || [];
            
            updateKPIs(data);
            populateQueue(data.queue);
            populateResolvedTable(data.resolved_list);
            initCharts(data);
        }
    } catch (err) {
        console.error("Failed to fetch engineer data:", err);
    }
}

function updateKPIs(data) {
    const kpis = document.querySelectorAll('.kpi-value');
    if (kpis.length >= 6) {
        kpis[0].textContent = data.assigned;
        kpis[1].textContent = data.overdue;
        kpis[2].textContent = data.assigned > 0 ? 'Today' : '-';
        kpis[3].textContent = data.assigned > 0 ? '0.0h' : '0.0h';
        kpis[4].textContent = data.sla_pct + '%';
        kpis[5].textContent = data.resolved_total;
    }
}

function populateQueue(tickets) {
    // Use the actual tbody ID from the HTML
    const tbody = document.getElementById('engineer-queue-body');
    if (!tbody) return;

    if (!tickets || tickets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:30px; color:var(--text-secondary);">Queue is clear. No active incidents.</td></tr>';
        return;
    }

    tbody.innerHTML = tickets.map(t => {
        const priorityClass = t.priority === 'Critical' ? 'critical' : (t.priority === 'High' ? 'high' : (t.priority === 'Medium' ? 'med' : 'low'));
        const now = new Date();
        const slaDeadline = new Date(t.sla_deadline + 'Z');
        const slaBreached = now > slaDeadline;
        const slaText = slaBreached ? 'BREACHED' : 'On Track';
        const slaClass = slaBreached ? 'critical' : 'resolved';

        return `
            <tr style="cursor:pointer;" onclick="openTicketDetail(${t.id})">
                <td>#INC-${t.id}</td>
                <td>
                    <div class="incident-cell">
                        <span class="inc-title">${t.subject}</span>
                        <span class="inc-subtext">${t.service_area} | ${t.creator_name || 'Unknown'}</span>
                    </div>
                </td>
                <td><span class="priority ${priorityClass}">${t.priority}</span></td>
                <td><span class="status ${slaClass}" style="font-size:11px;">${slaText}</span></td>
                <td>${t.environment || '-'}</td>
                <td>
                    <div class="action-group">
                        ${t.status === 'Open' ? `<button class="primary-btn sm" title="Accept" onclick="event.stopPropagation(); updateStatus(${t.id}, 'In Progress')"><i class="fas fa-play"></i> Accept</button>` : ''}
                        <button class="primary-btn sm" style="background:#10b981;" title="Resolve" onclick="event.stopPropagation(); updateStatus(${t.id}, 'Resolved')"><i class="fas fa-check"></i> Resolve</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function populateResolvedTable(tickets) {
    const tbody = document.getElementById('resolved-tickets-body');
    if (!tbody) return;

    if (!tickets || tickets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:30px; color:var(--text-secondary);">No resolution history yet.</td></tr>';
        return;
    }

    tbody.innerHTML = tickets.map(t => `
        <tr style="cursor:pointer;" onclick="openTicketDetail(${t.id})">
            <td>#INC-${t.id}</td>
            <td><span class="inc-title">${t.subject}</span></td>
            <td>${new Date(t.updated_at + 'Z').toLocaleDateString()}</td>
            <td><span class="status resolved">RESOLVED</span></td>
        </tr>
    `).join('');
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

        const priorityEl = document.getElementById('modal-priority');
        priorityEl.textContent = t.priority;
        priorityEl.className = 'badge ' + (t.priority === 'Critical' ? 'badge-critical' : 'badge-urgent');

        const statusEl = document.getElementById('modal-status');
        statusEl.textContent = t.status;
        const statusClass = t.status === 'Resolved' ? 'resolved' : (t.status === 'In Progress' ? 'prog' : 'open');
        statusEl.className = 'status ' + statusClass;

        const slaEl = document.getElementById('modal-sla-countdown');
        const now = new Date();
        const slaDeadline = new Date(t.sla_deadline + 'Z');
        if (t.status === 'Resolved' || t.status === 'Closed') {
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

        document.getElementById('modal-created').textContent = new Date(t.created_at + 'Z').toLocaleDateString();

        // Activity Feed (Comments)
        const commentsDiv = document.getElementById('modal-comments');
        if (data.comments && data.comments.length > 0) {
            commentsDiv.innerHTML = data.comments.map(c => `
                <div class="timeline-item">
                    <div class="timeline-point"></div>
                    <div class="timeline-info">${c.author_name} | ${new Date(c.created_at + 'Z').toLocaleString()}</div>
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

async function updateStatus(ticketId, status) {
    try {
        const res = await fetch(`${API_BASE}/api/tickets/${ticketId}/status`, {
            method: 'PUT',
            headers: authHeaders(),
            body: JSON.stringify({ status })
        });
        const data = await res.json();
        if (data.success) {
            refreshData();
        } else {
            alert(data.message);
        }
    } catch (err) {
        console.error("Status update failed:", err);
    }
}

function initCharts(data) {
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } }
    };

    // Resolution Velocity Chart
    const ctxEng = document.getElementById('engineerChart');
    if (ctxEng) {
        new Chart(ctxEng, {
            type: 'bar',
            data: {
                labels: ['Assigned', 'Overdue', 'Resolved'],
                datasets: [{
                    label: 'Tickets',
                    data: [data.assigned, data.overdue, data.resolved_total],
                    backgroundColor: ['#3b82f6', '#ef4444', '#10b981'],
                    borderRadius: 6
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { color: '#64748b', stepSize: 1 } },
                    x: { grid: { display: false }, ticks: { color: '#64748b', font: { weight: '600' } } }
                }
            }
        });
    }

    // MTTR Trend mini chart
    const ctxMttr = document.getElementById('mttrTrendChart');
    if (ctxMttr) {
        new Chart(ctxMttr, {
            type: 'line',
            data: {
                labels: ['', '', '', '', ''],
                datasets: [{
                    data: [0, 0, 0, 0, data.resolved_total > 0 ? 1.2 : 0],
                    borderColor: '#22d3ee',
                    borderWidth: 2,
                    tension: 0.4,
                    pointRadius: 0,
                    fill: true,
                    backgroundColor: 'rgba(34, 211, 238, 0.05)'
                }]
            },
            options: { ...commonOptions, scales: { x: { display: false }, y: { display: false } } }
        });
    }
}

function logout() {
    localStorage.clear();
    window.location.href = 'login.html';
}

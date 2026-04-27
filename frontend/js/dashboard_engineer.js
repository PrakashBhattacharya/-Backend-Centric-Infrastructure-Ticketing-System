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
            populateQueue(data.queue || []);
            populateResolvedTable(data.resolved_list || []);
            populateSlaMonitor(data.queue || []);
            populateActivityFeed(data.queue || []);
            initCharts(data);
        }
    } catch (err) {
        console.error("Failed to fetch engineer data:", err);
    }
}

function updateKPIs(data) {
    const kpis = document.querySelectorAll('.kpi-value');
    if (kpis.length >= 6) {
        kpis[0].textContent = data.assigned || 0;
        kpis[1].textContent = data.overdue || 0;
        // KPI[2] = tickets due today (SLA deadline within 24h)
        const dueToday = (data.queue || []).filter(t => {
            if (t.status === 'Resolved' || t.status === 'Closed' || t.status === 'Pending Approval') return false;
            const deadline = parseDate(t.sla_deadline);
            const diff = deadline - new Date();
            return diff > 0 && diff < 86400000;
        }).length;
        kpis[2].textContent = dueToday;
        kpis[3].textContent = data.mttr || '0.0h';
        kpis[4].textContent = (data.sla_pct || 0) + '%';
        kpis[5].textContent = data.resolved_total || 0;
    }

    // Resolution Score
    const scoreEl = document.getElementById('res-score-display');
    if (scoreEl) {
        const score = data.res_score ?? 0.0;
        const color = score >= 8 ? '#10b981' : score >= 5 ? '#f59e0b' : '#ef4444';
        scoreEl.innerHTML = `<span style="color:${color}">${score.toFixed(1)}</span><span>/10</span>`;
    }

    // Reopen rate (placeholder — 0% until backend tracks reopens)
    const reopenEl = document.getElementById('reopen-rate-display');
    if (reopenEl) {
        reopenEl.textContent = '0.0%';
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
        const slaDeadline = parseDate(t.sla_deadline);
        const slaBreached = t.sla_breached === true || now > slaDeadline;
        const slaText = slaBreached ? 'BREACHED' : 'On Track';
        const slaClass = slaBreached ? 'critical' : 'resolved';
        const rejectionNote = t.rejection_note && t.rejection_note.trim();

        return `
            <tr style="cursor:pointer;" onclick="openTicketDetail(${t.id})">
                <td>#INC-${t.id}</td>
                <td>
                    <div class="incident-cell">
                        <span class="inc-title">${t.subject}</span>
                        <span class="inc-subtext">${t.service_area} | ${t.creator_name || 'Unknown'}</span>
                        ${rejectionNote ? `
                            <div style="margin-top:6px; padding:6px 10px; background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.25); border-radius:6px; font-size:11px; color:#f87171; line-height:1.5;">
                                <i class="fas fa-times-circle" style="margin-right:5px;"></i><strong>Rejected:</strong> ${rejectionNote}
                            </div>
                        ` : ''}
                    </div>
                </td>
                <td><span class="priority ${priorityClass}">${t.priority}</span></td>
                <td><span class="status ${slaClass}" style="font-size:11px;">${slaText}</span></td>
                <td>${t.environment || '-'}</td>
                <td>
                    <div class="action-group">
                        ${t.status === 'Open' ? `<button class="primary-btn sm" title="Accept" onclick="event.stopPropagation(); updateStatus(${t.id}, 'In Progress')"><i class="fas fa-play"></i> Accept</button>` : ''}
                        ${t.status === 'In Progress' ? `
                            <button class="primary-btn sm" style="background:#f59e0b; color:#0f172a;" title="Submit for Approval" onclick="event.stopPropagation(); updateStatus(${t.id}, 'Pending Approval')"><i class="fas fa-paper-plane"></i> Submit</button>
                            ${!slaBreached ? `<button class="primary-btn sm" style="background:rgba(99,102,241,0.85); color:#fff;" title="Request SLA Extension" onclick="event.stopPropagation(); openSlaExtModal(${t.id})"><i class="fas fa-clock"></i> Extend SLA</button>` : ''}
                        ` : ''}
                        ${t.status === 'Pending Approval' ? `<span style="font-size:11px; color:#f59e0b; font-weight:600;"><i class="fas fa-hourglass-half"></i> Awaiting Admin</span>` : ''}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function populateSlaMonitor(tickets) {
    const container = document.querySelector('.sla-monitor-list');
    if (!container) return;

    const active = tickets.filter(t => t.status !== 'Resolved' && t.status !== 'Closed');
    if (active.length === 0) {
        container.innerHTML = '<div style="text-align:center; color:var(--text-secondary); padding:20px;">No Active SLAs</div>';
        return;
    }

    // Sort by deadline ascending
    active.sort((a, b) => parseDate(a.sla_deadline) - parseDate(b.sla_deadline));

    container.innerHTML = active.slice(0, 5).map(t => {
        const now = new Date();
        const deadline = parseDate(t.sla_deadline);
        const diff = deadline - now;
        const breached = diff <= 0 || t.sla_breached;
        const hours = Math.floor(Math.abs(diff) / 3600000);
        const mins = Math.floor((Math.abs(diff) % 3600000) / 60000);
        const timeText = breached ? 'BREACHED' : `${hours}h ${mins}m`;
        const color = breached ? '#ef4444' : (diff < 7200000 ? '#f59e0b' : '#10b981');
        const priorityClass = t.priority === 'Critical' ? 'critical' : (t.priority === 'High' ? 'high' : 'med');

        return `
            <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid rgba(255,255,255,0.04);">
                <div>
                    <div style="font-size:12px; font-weight:600; color:#f1f5f9;">#INC-${t.id}</div>
                    <div style="font-size:11px; color:#64748b; margin-top:2px;">${(t.subject || '').substring(0, 28)}${t.subject && t.subject.length > 28 ? '…' : ''}</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:12px; font-weight:700; color:${color};">${timeText}</div>
                    <span class="priority ${priorityClass}" style="font-size:10px;">${t.priority}</span>
                </div>
            </div>
        `;
    }).join('');
}

function populateActivityFeed(tickets) {
    const container = document.querySelector('.activity-timeline');
    if (!container) return;

    if (!tickets || tickets.length === 0) {
        container.innerHTML = '<div style="text-align:center; color:var(--text-secondary); padding:20px;">No Recent Activity</div>';
        return;
    }

    // Show recently updated tickets as activity
    const recent = [...tickets]
        .sort((a, b) => parseDate(b.updated_at) - parseDate(a.updated_at))
        .slice(0, 6);

    container.innerHTML = recent.map(t => {
        const statusClass = t.status === 'Resolved' ? 'resolved' : (t.status === 'In Progress' ? 'prog' : 'open');
        const dt = parseDate(t.updated_at);
        const timeStr = isNaN(dt) ? '-' : dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return `
            <div style="display:flex; gap:10px; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.04); align-items:flex-start;">
                <div style="width:6px; height:6px; border-radius:50%; background:#3b82f6; margin-top:5px; flex-shrink:0;"></div>
                <div style="flex:1; min-width:0;">
                    <div style="font-size:12px; color:#f1f5f9; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">#INC-${t.id} — ${t.subject || ''}</div>
                    <div style="font-size:11px; color:#64748b; margin-top:2px;"><span class="status ${statusClass}" style="font-size:10px;">${t.status}</span> · ${timeStr}</div>
                </div>
            </div>
        `;
    }).join('');
}

function populateResolvedTable(tickets) {    const tbody = document.getElementById('resolved-tickets-body');
    if (!tbody) return;

    if (!tickets || tickets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:30px; color:var(--text-secondary);">No resolution history yet.</td></tr>';
        return;
    }

    tbody.innerHTML = tickets.map(t => `
        <tr style="cursor:pointer;" onclick="openTicketDetail(${t.id})">
            <td>#INC-${t.id}</td>
            <td><span class="inc-title">${t.subject}</span></td>
            <td>${parseDate(t.updated_at).toLocaleDateString()}</td>
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

        // Activity Feed (Comments)
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
    const chartFont = {
        family: "'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        size: 11,
        weight: '600'
    };

    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 15, bottom: 5, left: 10, right: 10 } },
        plugins: { 
            legend: { display: false },
            tooltip: {
                backgroundColor: 'rgba(10, 14, 28, 0.98)',
                titleFont: { family: chartFont.family, size: 12, weight: '700' },
                bodyFont: { family: chartFont.family, size: 11 },
                titleColor: '#f1f5f9',
                bodyColor: '#94a3b8',
                borderColor: 'rgba(59, 130, 246, 0.2)',
                borderWidth: 1,
                padding: 10,
                cornerRadius: 8
            }
        },
        animation: {
            duration: 2000,
            easing: 'easeOutElastic'
        }
    };

    // Resolution Velocity Chart (Bar) — Upgraded with gradients
    const ctxEng = document.getElementById('engineerChart');
    if (ctxEng) {
        const ctx = ctxEng.getContext('2d');
        const gradBlue = ctx.createLinearGradient(0, 0, 0, 300);
        gradBlue.addColorStop(0, '#3b82f6'); gradBlue.addColorStop(1, 'rgba(59, 130, 246, 0.1)');
        
        const gradRed = ctx.createLinearGradient(0, 0, 0, 300);
        gradRed.addColorStop(0, '#ef4444'); gradRed.addColorStop(1, 'rgba(239, 68, 68, 0.1)');
        
        const gradGreen = ctx.createLinearGradient(0, 0, 0, 300);
        gradGreen.addColorStop(0, '#10b981'); gradGreen.addColorStop(1, 'rgba(16, 185, 129, 0.1)');

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Assigned', 'Overdue', 'Resolved'],
                datasets: [{
                    label: 'Tickets',
                    data: [data.assigned, data.overdue, data.resolved_total],
                    backgroundColor: [gradBlue, gradRed, gradGreen],
                    borderColor: ['#3b82f6', '#ef4444', '#10b981'],
                    borderWidth: 1,
                    borderRadius: 6
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    y: { 
                        beginAtZero: true, 
                        grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false }, 
                        ticks: { color: '#64748b', stepSize: 1, font: { size: 10 } } 
                    },
                    x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { weight: '600', size: 11 } } }
                }
            }
        });
    }

    // MTTR Trend mini chart — Real Data Trend
    const ctxMttr = document.getElementById('mttrTrendChart');
    if (ctxMttr) {
        const ctx = ctxMttr.getContext('2d');
        const gradFill = ctx.createLinearGradient(0, 0, 0, 50);
        gradFill.addColorStop(0, 'rgba(34, 211, 238, 0.3)');
        gradFill.addColorStop(1, 'rgba(34, 211, 238, 0)');

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['', '', '', '', ''],
                datasets: [{
                    data: data.mttr_trend || [0, 0, 0, 0, 0],
                    borderColor: '#22d3ee',
                    borderWidth: 2,
                    tension: 0.45,
                    pointRadius: 0,
                    fill: true,
                    backgroundColor: gradFill
                }]
            },
            options: { 
                ...commonOptions, 
                animations: { tension: { duration: 1000, easing: 'linear' } },
                scales: { x: { display: false }, y: { display: false } } 
            }
        });
    }
}

window.logout = function() {
    localStorage.clear();
    window.location.href = 'login.html';
};

// ─── Profile Dropdown ────────────────────────────────────────────────────────
function _closePd() {
    const dropdown = document.getElementById('profile-dropdown');
    const backdrop = document.getElementById('pd-backdrop');
    if (dropdown) dropdown.classList.remove('open');
    if (backdrop) backdrop.remove();
    document.body.classList.remove('pd-open');
}

function toggleProfileDropdown() {
    const dropdown = document.getElementById('profile-dropdown');
    if (!dropdown) return;

    if (dropdown.classList.contains('open')) {
        _closePd();
        return;
    }

    // Create backdrop
    let backdrop = document.getElementById('pd-backdrop');
    if (!backdrop) {
        backdrop = document.createElement('div');
        backdrop.id = 'pd-backdrop';
        backdrop.className = 'pd-backdrop';
        backdrop.addEventListener('click', _closePd);
        document.body.appendChild(backdrop);
    }
    document.body.classList.add('pd-open');

    // Populate from localStorage immediately
    const name  = localStorage.getItem('user_name')  || '—';
    const email = localStorage.getItem('user_email') || '—';
    const role  = localStorage.getItem('user_role')  || '—';
    const uid   = localStorage.getItem('user_id')    || '—';

    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

    set('dd-name',   name);
    set('dd-email',  email);
    set('dd-email2', email);
    set('dd-uid',    uid ? '#' + String(uid).padStart(4, '0') : '—');

    // Decode JWT for session expiry
    try {
        const token = localStorage.getItem('auth_token');
        const payload = JSON.parse(atob(token.split('.')[1]));
        if (payload.exp) {
            const exp = new Date(payload.exp * 1000);
            const now = new Date();
            const diffMs = exp - now;
            if (diffMs > 0) {
                const h = Math.floor(diffMs / 3600000);
                const m = Math.floor((diffMs % 3600000) / 60000);
                set('dd-session', h > 0 ? h + 'h ' + m + 'm' : m + 'm');
            } else {
                set('dd-session', 'Expired');
            }
        }
    } catch(e) { set('dd-session', '—'); }

    dropdown.classList.add('open');

    // Fetch live stats from /api/me
    const token = localStorage.getItem('auth_token');
    fetch(window.API_BASE + '/api/me', {
        headers: { 'Authorization': 'Bearer ' + token }
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) return;
        const u = data.user;

        set('dd-name',   u.full_name || name);
        set('dd-email',  u.email || email);
        set('dd-email2', u.email || email);

        // Joined date
        if (u.created_at) {
            try {
                const d = new Date(u.created_at.replace(' ', 'T') + 'Z');
                set('dd-since', d.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' }));
            } catch(e) { set('dd-since', u.created_at); }
        }

        // Stats
        const s = u.stats || {};
        if (u.role === 'member') {
            set('dd-s1', s.total_tickets   ?? '—');
            set('dd-s2', s.open_tickets    ?? '—');
            set('dd-s3', s.resolved_tickets ?? '—');
        } else if (u.role === 'engineer') {
            set('dd-s1', s.assigned_tickets  ?? '—');
            set('dd-s2', s.resolved_tickets  ?? '—');
            set('dd-s3', s.avg_mttr          ?? '—');
        } else {
            set('dd-s1', s.total_tickets ?? '—');
            set('dd-s2', s.engineers     ?? '—');
            set('dd-s3', s.members       ?? '—');
        }
    })
    .catch(() => {});
}

// Backdrop click closes dropdown (handled on the backdrop element itself)

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
    if (!AUTH_TOKEN) {
        window.location.href = 'login.html';
        return false;
    }
    return true;
}

// ─── Modal Global Functions ─────────────────────────────────────────────────
function openModal(id) {
    document.getElementById(id).style.display = 'flex';
}

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
}

// ─── Global State ───────────────────────────────────────────────────────────
const KNOWLEDGE_BASE_DATA = {
    'Getting Started': {
        subtitle: 'New User Onboarding Guide',
        content: `
            <p>Welcome to InfraTick! Follow these steps to manage your infrastructure incidents:</p>
            <ul style="margin-left: 20px; margin-top: 10px;">
                <li><strong>Submit Incident:</strong> Click "New Ticket" at the top right. Detailed descriptions speed up resolution.</li>
                <li><strong>Track Status:</strong> Monitor real-time status (Open, In Progress, Resolved) in your Archive.</li>
                <li><strong>SLA Monitoring:</strong> Each ticket has a deadline. Critical issues get faster response.</li>
                <li><strong>Engagement:</strong> Your assigned engineer may reach out via internal channels if more data is needed.</li>
            </ul>
        `
    },
    'SLA Guidelines': {
        subtitle: 'Service Level Agreement Standards',
        content: `
            <table style="width:100%; border-collapse: collapse; margin-top:10px;">
                <tr style="border-bottom: 2px solid rgba(255,255,255,0.1);">
                    <th style="text-align:left; padding:8px;">Priority</th>
                    <th style="text-align:left; padding:8px;">Response Time</th>
                    <th style="text-align:left; padding:8px;">Resolution SLA</th>
                </tr>
                <tr><td style="padding:8px; color:#f87171;">Critical</td><td style="padding:8px;">15-30m</td><td style="padding:8px;">2 Hours</td></tr>
                <tr><td style="padding:8px; color:#fbbf24;">High</td><td style="padding:8px;">1-2 Hours</td><td style="padding:8px;">8 Hours</td></tr>
                <tr><td style="padding:8px; color:#3b82f6;">Medium</td><td style="padding:8px;">4 Hours</td><td style="padding:8px;">20 Hours</td></tr>
                <tr><td style="padding:8px; color:#94a3b8;">Low</td><td style="padding:8px;">Next Bus. Day</td><td style="padding:8px;">50 Hours</td></tr>
            </table>
        `
    },
    'Troubleshooting': {
        subtitle: 'Initial Diagnostic Protocol',
        content: `
            <p>Before submitting a ticket, please check the following:</p>
            <ul style="margin-left: 20px; margin-top: 10px;">
                <li><strong>Connectivity:</strong> Run <code>ping -c 4 [resource_ip]</code> to check latency.</li>
                <li><strong>Auth:</strong> Ensure your tokens / IAM roles have not expired (check Identity Manager).</li>
                <li><strong>Logs:</strong> Capture the exact error code (e.g., HTTP 504, Connection Timeout).</li>
                <li><strong>Environment:</strong> Verify if the issue is global or limited to your specific cluster.</li>
            </ul>
        `
    },
    'FAQs': {
        subtitle: 'Commonly Asked Questions',
        content: `
            <div style="margin-top:10px;">
                <div style="margin-bottom:12px;"><strong>Q: How do I escalate a ticket?</strong><br>A: Tickets nearing SLA breach are automatically escalated to Team Leads.</div>
                <div style="margin-bottom:12px;"><strong>Q: Can I reopen a resolved ticket?</strong><br>A: Yes, if the issue persists, you can request a reopen via the ticket detail view.</div>
                <div style="margin-bottom:12px;"><strong>Q: How are priorities defined?</strong><br>A: Priorities are defined by Production Impact. Dev/Staging issues should be Medium or Low.</div>
            </div>
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

// ─── Main Init ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    if (!checkAuth()) return;

    // Set user info in sidebar
    const userName = localStorage.getItem('user_name') || 'Member';
    const userNameEl = document.querySelector('.user-name');
    const avatarEl = document.querySelector('.profile-avatar');
    if (userNameEl) userNameEl.textContent = userName;
    if (avatarEl) avatarEl.textContent = userName.charAt(0).toUpperCase();

    // ─── FETCH DASHBOARD DATA ───────────────────────────────────────────
    let dbData = {
        active: 0, resolved: 0, total: 0, urgent: 0, breached: 0, sla_pct: 0,
        priorityData: [0, 0, 0, 0],
        tickets: []
    };
    window.allMemberTickets = []; // Store for filtering

    try {
        const res = await fetch(`${API_BASE}/api/dashboard/member`, { headers: authHeaders() });
        const json = await res.json();
        if (json.success) {
            dbData = json;
            window.allMemberTickets = json.tickets || [];
        }
    } catch (err) {
        console.error("Backend fetch failed:", err);
    }

    // ─── UPDATE KPI CARDS ───────────────────────────────────────────────
    const kpiValues = document.querySelectorAll('.kpi-value');
    if (kpiValues.length >= 6) {
        kpiValues[0].textContent = dbData.active;
        kpiValues[1].textContent = dbData.resolved;
        kpiValues[2].textContent = dbData.mttr || '0.0h';
        kpiValues[3].textContent = dbData.sla_pct + '%';
        kpiValues[4].textContent = dbData.urgent;
        kpiValues[5].textContent = dbData.breached;
    }

    // ─── POPULATE TICKETS TABLE ─────────────────────────────────────────
    populateTicketTable(dbData.tickets);

    // ─── CHARTS (Ultra-Polish Upgrade) ─────────────────────────────────
    const chartFont = {
        family: "'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        size: 11,
        weight: '500'
    };

    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 10, bottom: 10, left: 5, right: 5 } },
        plugins: {
            legend: {
                position: 'bottom',
                labels: { 
                    color: '#94a3b8', 
                    font: chartFont, 
                    usePointStyle: true,
                    pointStyle: 'circle',
                    padding: 20
                }
            },
            tooltip: {
                backgroundColor: 'rgba(10, 14, 28, 0.95)',
                titleFont: { family: chartFont.family, size: 13, weight: '700' },
                bodyFont: { family: chartFont.family, size: 12 },
                titleColor: '#f1f5f9',
                bodyColor: '#94a3b8',
                borderColor: 'rgba(34, 211, 238, 0.15)',
                borderWidth: 1,
                padding: 12,
                cornerRadius: 10,
                displayColors: true,
                boxShadow: '0 8px 30px rgba(0,0,0,0.5)'
            }
        },
        animation: {
            duration: 2500,
            easing: 'easeOutElastic'
        }
    };

    // 1. Resolution Velocity Chart (Bar) — upgraded with gradients
    const ctxMember = document.getElementById('memberChart');
    if (ctxMember) {
        const ctx = ctxMember.getContext('2d');
        
        // Define Gradients
        const gradCrit = ctx.createLinearGradient(0, 0, 0, 400);
        gradCrit.addColorStop(0, '#f87171'); gradCrit.addColorStop(1, 'rgba(248, 113, 113, 0.1)');
        
        const gradHigh = ctx.createLinearGradient(0, 0, 0, 400);
        gradHigh.addColorStop(0, '#fbbf24'); gradHigh.addColorStop(1, 'rgba(251, 191, 36, 0.1)');
        
        const gradMed = ctx.createLinearGradient(0, 0, 0, 400);
        gradMed.addColorStop(0, '#3b82f6'); gradMed.addColorStop(1, 'rgba(59, 130, 246, 0.1)');
        
        const gradLow = ctx.createLinearGradient(0, 0, 0, 400);
        gradLow.addColorStop(0, '#94a3b8'); gradLow.addColorStop(1, 'rgba(148, 163, 184, 0.1)');

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Critical', 'High', 'Medium', 'Low'],
                datasets: [{
                    label: 'TICKETS',
                    data: dbData.priorityData,
                    backgroundColor: [gradCrit, gradHigh, gradMed, gradLow],
                    borderColor: ['#f87171', '#fbbf24', '#3b82f6', '#94a3b8'],
                    borderWidth: 1,
                    borderRadius: 8,
                    hoverBorderWidth: 2
                }]
            },
            options: {
                ...commonOptions,
                plugins: { ...commonOptions.plugins, legend: { display: false } },
                scales: {
                    y: { 
                        beginAtZero: true, 
                        grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false }, 
                        ticks: { color: '#64748b', stepSize: 1, font: { size: 10 } } 
                    },
                    x: { 
                        grid: { display: false }, 
                        ticks: { color: '#94a3b8', font: { weight: '600', size: 10 } } 
                    }
                }
            }
        });
    }

    // 2. Priority Breakdown Chart (Donut)
    const ctxPriority = document.getElementById('priorityChart');
    if (ctxPriority) {
        new Chart(ctxPriority.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'],
                datasets: [{
                    data: dbData.priorityData,
                    backgroundColor: ['#f87171', '#fbbf24', '#3b82f6', '#64748b'],
                    borderColor: '#0a0c14',
                    borderWidth: 4,
                    hoverOffset: 15
                }]
            },
            options: { 
                ...commonOptions, 
                cutout: '78%',
                plugins: {
                    ...commonOptions.plugins,
                    legend: { ...commonOptions.plugins.legend, position: 'right' }
                }
            }
        });
    }

    // 3. Backlog Trend Chart (Line) — real data trend
    const ctxBacklog = document.getElementById('backlogChart');
    if (ctxBacklog) {
        const ctx = ctxBacklog.getContext('2d');
        const gradFill = ctx.createLinearGradient(0, 0, 0, 300);
        gradFill.addColorStop(0, 'rgba(34, 211, 238, 0.2)');
        gradFill.addColorStop(1, 'rgba(34, 211, 238, 0)');

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['6d ago', '5d ago', '4d ago', '3d ago', '2d ago', 'Yesterday', 'Today'],
                datasets: [{
                    label: 'DAILY SUBMISSIONS',
                    data: dbData.backlogTrendData || [0, 0, 0, 0, 0, 0, dbData.active],
                    borderColor: '#22d3ee',
                    backgroundColor: gradFill,
                    borderWidth: 3,
                    fill: true,
                    tension: 0.45,
                    pointRadius: 4,
                    pointBackgroundColor: '#22d3ee',
                    pointBorderColor: '#0a0c14',
                    pointBorderWidth: 2,
                    pointHoverRadius: 7
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#64748b', stepSize: 1 } },
                    x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 9 } } }
                }
            }
        });
    }

    // 4. SLA Status Chart (Donut) — Corrected logic for ALL tickets
    const ctxSla = document.getElementById('slaDonutChart');
    if (ctxSla) {
        const total = dbData.total || 0;
        const breached = dbData.breached || 0;
        const met = Math.max(0, total - breached);
        
        new Chart(ctxSla.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['MET SLA', 'BREACHED'],
                datasets: [{
                    data: [met, breached],
                    backgroundColor: ['#10b981', '#ef4444'],
                    borderColor: '#0a0c14',
                    borderWidth: 5,
                    hoverOffset: 10
                }]
            },
            options: { 
                ...commonOptions, 
                cutout: '82%',
                plugins: {
                    ...commonOptions.plugins,
                    legend: { ...commonOptions.plugins.legend, position: 'bottom' }
                }
            }
        });
    }

    // ─── NAVIGATION ─────────────────────────────────────────────────────
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

    // ─── FILTERING LOGIC ───────────────────────────────────────────────
    const filterStatus = document.getElementById('filter-status');
    const filterPriority = document.getElementById('filter-priority');
    const filterSla = document.getElementById('filter-sla');

    const applyFilters = () => {
        const status = filterStatus.value;
        const priority = filterPriority.value;
        const sla = filterSla.value;

        const filtered = window.allMemberTickets.filter(t => {
            const matchStatus = (status === 'All Status' || t.status === status);
            const matchPriority = (priority === 'All Priorities' || t.priority === priority);

            let matchSla = true;
            if (sla !== 'All') {
                const now = new Date();
                const deadline = parseDate(t.sla_deadline);
                const isBreached = t.sla_breached === true || (now > deadline && t.status !== 'Resolved' && t.status !== 'Closed');
                matchSla = (sla === 'Breached' ? isBreached : !isBreached);
            }

            return matchStatus && matchPriority && matchSla;
        });

        populateTicketTable(filtered);
    };

    if (filterStatus) filterStatus.addEventListener('change', applyFilters);
    if (filterPriority) filterPriority.addEventListener('change', applyFilters);
    if (filterSla) filterSla.addEventListener('change', applyFilters);

    // ─── GLOBAL SEARCH ───
    const globalSearch = document.getElementById('global-search');
    if (globalSearch) {
        globalSearch.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            const filtered = window.allMemberTickets.filter(t => 
                (t.subject || '').toLowerCase().includes(query) || 
                (t.id || '').toString().includes(query)
            );
            populateTicketTable(filtered);
        });
    }

    console.log("Member Dashboard initialized with filtering.");
});

// ─── Populate Ticket Table ──────────────────────────────────────────────────
function populateTicketTable(tickets) {
    const tbody = document.querySelector('#tickets .table-wrapper tbody');
    if (!tbody) return;

    if (!tickets || tickets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 30px;">No tickets found. Submit a new incident to get started.</td></tr>';
        return;
    }

    tbody.innerHTML = tickets.map(t => {
        const priorityClass = t.priority === 'Critical' ? 'critical' : (t.priority === 'High' ? 'high' : (t.priority === 'Medium' ? 'med' : 'low'));
        const statusClass = t.status === 'Resolved' ? 'resolved' : (t.status === 'In Progress' ? 'prog' : (t.status === 'Open' ? 'open' : 'resolved'));
        const now = new Date();
        const slaDeadline = parseDate(t.sla_deadline);
        const slaBreached = t.sla_breached === true || (now > slaDeadline && t.status !== 'Resolved' && t.status !== 'Closed');
        const slaText = slaBreached ? 'Breached' : (t.status === 'Resolved' || t.status === 'Closed' ? 'Met' : 'On Track');
        const slaClass = slaBreached ? 'breached' : (t.status === 'Resolved' || t.status === 'Closed' ? 'resolved' : 'open');

        return `<tr style="cursor:pointer;" onclick="openTicketDetail(${t.id})">
            <td>#INC-${t.id}</td>
            <td><span class="inc-title">${t.subject}</span></td>
            <td><span class="priority ${priorityClass}">${t.priority}</span></td>
            <td><span class="status ${statusClass}">${t.status}</span></td>
            <td><span class="status ${slaClass}">${slaText}</span></td>
            <td>${parseDate(t.created_at).toLocaleDateString()}</td>
        </tr>`;
    }).join('');
}

// ─── Ticket Detail Modal ────────────────────────────────────────────────────
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

        modal.style.display = 'flex';
    } catch (err) {
        console.error('Error fetching ticket detail:', err);
    }
}

// ─── Submit New Ticket ──────────────────────────────────────────────────────
async function submitNewTicket(e) {
    e.preventDefault();

    const priority = document.getElementById('ticket-priority').value;
    if (!priority) {
        alert('Please select a priority level before submitting.');
        return;
    }

    const subject = document.getElementById('ticket-subject').value.trim();
    const description = document.getElementById('ticket-desc').value.trim();
    const service_area = document.getElementById('ticket-service').value;
    const environment = document.getElementById('ticket-env').value;

    if (!subject) {
        alert('Please enter an incident subject.');
        return;
    }

    const submitBtn = document.querySelector('#new-ticket-form .primary-btn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
    }

    try {
        const res = await fetch(`${API_BASE}/api/tickets`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ subject, description, service_area, environment, priority })
        });

        const data = await res.json();

        if (data.success) {
            alert(`✅ Ticket #INC-${data.ticket.id} created successfully!\n\nPriority: ${priority}\nSLA Deadline: ${parseDate(data.ticket.sla_deadline).toLocaleString()}`);

            // Reset form
            document.getElementById('new-ticket-form').reset();
            document.querySelectorAll('.pri-btn').forEach(b => b.classList.remove('selected'));
            document.getElementById('sla-banner').style.display = 'none';
            document.getElementById('ticket-priority').value = '';
            closeModal('ticket-modal');

            // Refresh dashboard data
            location.reload();
        } else {
            alert('Failed to create ticket: ' + data.message);
        }
    } catch (err) {
        console.error('Error creating ticket:', err);
        alert('Error connecting to backend.');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Incident';
        }
    }
}

// Close modal when clicking outside
window.onclick = function (event) {
    if (event.target && event.target.classList.contains('modal')) {
        event.target.style.display = "none";
    }
}

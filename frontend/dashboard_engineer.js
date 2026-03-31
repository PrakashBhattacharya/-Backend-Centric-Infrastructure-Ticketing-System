document.addEventListener('DOMContentLoaded', async () => {
    // FETCH DATA
    let dbData = {
        resolvedData: [0, 0, 0, 0, 0],
        mttrData: [0, 0, 0, 0, 0, 0, 0],
        telemetryData: [0, 0, 0],
        resolvedTickets: []
    };
    try {
        const res = await fetch('http://127.0.0.1:5000/api/engineer/queue');
        const json = await res.json();
        if (json.success) dbData = json;
    } catch(err) {
        console.error("Backend fetch failed:", err);
    }

    // 1. Performance Charts
    const initPerformanceCharts = () => {
        try {
            // Main Bar Chart (Tickets Resolved)
            const canvasBar = document.getElementById('engineerChart');
            if (canvasBar) {
                const ctxBar = canvasBar.getContext('2d');
                const gradientResolved = ctxBar.createLinearGradient(0, 0, 400, 0);
                gradientResolved.addColorStop(0, '#3b82f6');
                gradientResolved.addColorStop(1, '#22d3ee');

                new Chart(ctxBar, {
                    type: 'bar',
                    data: {
                        labels: ['NETWORK', 'DATABASE', 'STORAGE', 'COMPUTE', 'SECURITY'],
                        datasets: [{
                            label: 'TICKETS RESOLVED (MTD)',
                            data: dbData.resolvedData,
                            backgroundColor: gradientResolved,
                            borderColor: '#0a0c14',
                            borderWidth: 2,
                            borderRadius: 8,
                            barThickness: 32,
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: { backgroundColor: 'rgba(8, 12, 24, 0.95)', padding: 12, cornerRadius: 10 }
                        },
                        scales: {
                            x: {
                                beginAtZero: true,
                                grid: { color: 'rgba(255,255,255,0.02)', drawBorder: false },
                                ticks: { color: '#64748b', font: { weight: '600' } }
                            },
                            y: {
                                grid: { display: false },
                                ticks: { color: '#f1f5f9', font: { size: 12, weight: '700' } }
                            }
                        }
                    }
                });
            }

            // MTTR Trend Chart (Mini Line)
            const canvasMttr = document.getElementById('mttrTrendChart');
            if (canvasMttr) {
                const ctxMttr = canvasMttr.getContext('2d');
                new Chart(ctxMttr, {
                    type: 'line',
                    data: {
                        labels: ['M', 'T', 'W', 'T', 'F', 'S', 'S'],
                        datasets: [{
                            data: dbData.mttrData,
                            borderColor: '#22d3ee',
                            backgroundColor: 'rgba(34, 211, 238, 0.05)',
                            borderWidth: 2,
                            tension: 0.4,
                            fill: true,
                            pointRadius: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: { x: { display: false }, y: { display: false } }
                    }
                });
            }
        } catch (e) {
            console.error('Error initializing Engineer charts:', e);
        }
    };

    initPerformanceCharts();

    // 2. Live SLA Countdown Timers
    const startSlaTimers = () => {
        try {
            const timers = document.querySelectorAll('.sla-timer');

            setInterval(() => {
                timers.forEach(timer => {
                    if (!timer.hasAttribute('data-expiry')) return;
                    let seconds = parseInt(timer.getAttribute('data-expiry'));
                    if (seconds > 0) {
                        seconds--;
                        timer.setAttribute('data-expiry', seconds);

                        const h = Math.floor(seconds / 3600);
                        const m = Math.floor((seconds % 3600) / 60);
                        const s = seconds % 60;

                        timer.textContent = `${h > 0 ? h + ':' : ''}${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;

                        // Visual urgency
                        if (seconds < 600) { // < 10 mins
                            timer.className = 'status breached sla-timer';
                        } else if (seconds < 1800) { // < 30 mins
                            timer.className = 'status orange sla-timer';
                        }
                    }
                });
            }, 1000);
        } catch (e) {
            console.error('Error in SLA timers:', e);
        }
    };

    startSlaTimers();

    // 3. Telemetry Simulation
    const simulateTelemetry = () => {
        try {
            const bars = document.querySelectorAll('.tel-bar');
            const vals = document.querySelectorAll('.tel-val');

            // Set initial telemetry data from backend instead of reading DOM style if available
            bars.forEach((bar, index) => {
                const initialVal = dbData.telemetryData[index] || 50;
                bar.style.width = initialVal + '%';
                if (vals[index]) vals[index].textContent = initialVal + '%';
            });

            setInterval(() => {
                bars.forEach((bar, index) => {
                    const currentWidth = parseInt(bar.style.width);
                    if (isNaN(currentWidth)) return;

                    const variation = Math.floor(Math.random() * 5) - 2; // -2 to +2
                    const newWidth = Math.max(5, Math.min(95, currentWidth + variation));
                    bar.style.width = newWidth + '%';
                    if (vals[index]) vals[index].textContent = newWidth + '%';

                    // Color shift based on intensity
                    if (newWidth > 80) bar.style.background = '#ef4444';
                    else if (newWidth > 60) bar.style.background = '#f59e0b';
                    else bar.style.background = index === 0 ? '#3b82f6' : (index === 1 ? '#22d3ee' : '#10b981');
                });
            }, 3000);
        } catch (e) {
            console.error('Error in Telemetry simulation:', e);
        }
    };

    simulateTelemetry();

    // 5. Populate Resolved Tickets (Performance View)
    const populateResolvedTickets = () => {
        try {
            const body = document.getElementById('resolved-tickets-body');
            if (!body) return;

            const resolvedData = dbData.resolvedTickets;

            if (resolvedData.length === 0) {
                body.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-secondary); padding: 30px;">No recently resolved tickets.</td></tr>';
                return;
            }

            body.innerHTML = resolvedData.map(ticket => `
                <tr>
                    <td>#INC-${ticket.id}</td>
                    <td><div class="inc-title">${ticket.title}</div></td>
                    <td>${ticket.time}</td>
                    <td><span class="status resolved">${ticket.status}</span></td>
                </tr>
            `).join('');
        } catch (e) {
            console.error('Error populating resolved tickets:', e);
        }
    };

    populateResolvedTickets();

    // 4. View Logic Resize
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

            // Trigger chart resize
            window.dispatchEvent(new CustomEvent('dashboardViewChanged', { detail: { viewId } }));
        });
    });
});

// Smart Actions (Outside DOMContentLoaded to ensure global access if needed, though window attachment works inside too)
window.assignTicket = (id) => {
    alert(`Ticket #INC-${id} assigned to you. SLA tracking started.`);
    try {
        const row = document.querySelector(`button[onclick="assignTicket('${id}')"]`).closest('tr');
        if (row) {
            const statusCell = row.querySelector('.sla-timer');
            if (statusCell) {
                statusCell.className = 'status prog sla-timer';
                statusCell.textContent = 'In Progress';
                statusCell.removeAttribute('data-expiry'); // Stop timer effectively
            }
        }

        // Mock activity update
        const timeline = document.querySelector('.activity-timeline');
        if (timeline) {
            const newEntry = document.createElement('div');
            newEntry.className = 'activity-entry';
            newEntry.innerHTML = `<span class="activity-time">${new Date().getHours()}:${new Date().getMinutes().toString().padStart(2, '0')}</span>
                                  <span class="activity-desc">#INC-${id} acknowledged by Sarah J.</span>`;
            timeline.prepend(newEntry);
        }
    } catch (e) {
        console.error('Error in assignTicket DOM updates:', e);
    }
};

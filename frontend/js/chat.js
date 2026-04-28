// ─── InfraTick Chat ───────────────────────────────────────────────────────────
// Read from localStorage — set at login time
const AUTH_TOKEN = localStorage.getItem('auth_token');
const MY_ID      = parseInt(localStorage.getItem('user_id'), 10);
const MY_NAME    = localStorage.getItem('user_name') || 'Me';
const MY_ROLE    = localStorage.getItem('user_role') || 'member';

// API_BASE is set by config.js which loads before this file
function getBase() { return window.API_BASE || ''; }

function authHeaders() {
    return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${AUTH_TOKEN}` };
}

// Redirect if not logged in
if (!AUTH_TOKEN) { window.location.href = 'login.html'; }

// ─── State ────────────────────────────────────────────────────────────────────
let allUsers             = [];   // [{id, full_name, email, role}]
let activeChat           = null; // {type:'private'|'group', id, name}
let pollTimer            = null;
let lastMsgTime          = null;
let selectedGroupMembers = new Set();
let dmPickerCallback     = null; // stores the callback for DM user picker

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    // Set back button
    document.getElementById('back-btn').href = `dashboard_${MY_ROLE}.html`;

    // Show create-group button for admins only
    if (MY_ROLE === 'admin') {
        document.getElementById('new-group-btn').style.display = 'flex';
    }

    setupTabs();
    setupInput();
    setupModals();

    await loadUsers();
    await Promise.all([loadInbox(), loadGroups()]);
});

// ─── Load all users ───────────────────────────────────────────────────────────
async function loadUsers() {
    try {
        const res  = await fetch(`${getBase()}/api/chat/users`, { headers: authHeaders() });
        const data = await res.json();
        if (data.success) allUsers = data.users || [];
    } catch (e) { console.error('loadUsers:', e); }
}

// ─── Inbox ────────────────────────────────────────────────────────────────────
async function loadInbox() {
    try {
        const res  = await fetch(`${getBase()}/api/chat/inbox`, { headers: authHeaders() });
        const data = await res.json();
        renderInbox(data.conversations || []);
    } catch (e) { console.error('loadInbox:', e); }
}

function renderInbox(convs) {
    const list = document.getElementById('dm-list');
    if (!convs.length) {
        list.innerHTML = '<div class="chat-list-empty">No conversations yet.<br>Click <b>+</b> to start one.</div>';
        return;
    }
    list.innerHTML = convs.map(c => `
        <div class="chat-conv-item" data-type="private" data-id="${c.other_id}"
             onclick="openPrivateChat(${c.other_id}, ${JSON.stringify(c.other_name)}, ${JSON.stringify(c.other_role)})">
            <div class="chat-conv-avatar">${(c.other_name || '?').charAt(0).toUpperCase()}</div>
            <div class="chat-conv-info">
                <div class="chat-conv-name">${esc(c.other_name)}</div>
                <div class="chat-conv-preview">${esc(c.last_text || '')}</div>
            </div>
            <div class="chat-conv-meta">${fmtTime(c.last_at)}</div>
        </div>
    `).join('');
    highlightActive();
}

// ─── Groups ───────────────────────────────────────────────────────────────────
async function loadGroups() {
    try {
        const res  = await fetch(`${getBase()}/api/chat/groups`, { headers: authHeaders() });
        const data = await res.json();
        renderGroups(data.groups || []);
    } catch (e) { console.error('loadGroups:', e); }
}

function renderGroups(groups) {
    const list = document.getElementById('group-list');
    if (!groups.length) {
        list.innerHTML = '<div class="chat-list-empty">No groups yet.' +
            (MY_ROLE === 'admin' ? '<br>Click <b>+</b> to create one.' : '') + '</div>';
        return;
    }
    list.innerHTML = groups.map(g => `
        <div class="chat-conv-item" data-type="group" data-id="${g.id}"
             onclick="openGroupChat(${g.id}, ${JSON.stringify(g.name)}, ${g.member_count || 0})">
            <div class="chat-conv-avatar group"><i class="fas fa-users" style="font-size:14px;"></i></div>
            <div class="chat-conv-info">
                <div class="chat-conv-name">${esc(g.name)}</div>
                <div class="chat-conv-preview">${g.last_message ? esc(g.last_message) : (g.member_count || 0) + ' members'}</div>
            </div>
            <div class="chat-conv-meta">${fmtTime(g.last_at || g.created_at)}</div>
        </div>
    `).join('');
    highlightActive();
}

// ─── Open chats ───────────────────────────────────────────────────────────────
async function openPrivateChat(userId, userName, userRole) {
    stopPolling();
    activeChat   = { type: 'private', id: userId, name: userName };
    lastMsgTime  = null;

    document.getElementById('chat-empty').style.display  = 'none';
    document.getElementById('chat-window').style.display = 'flex';

    const av = document.getElementById('chat-avatar');
    av.textContent = (userName || '?').charAt(0).toUpperCase();
    av.className   = 'chat-header-avatar';
    document.getElementById('chat-name').textContent = userName;
    document.getElementById('chat-sub').textContent  = (userRole || '').charAt(0).toUpperCase() + (userRole || '').slice(1);
    document.getElementById('chat-info-btn').onclick  = null;

    document.getElementById('chat-messages').innerHTML = '';
    highlightActive();
    await fetchMessages();
    startPolling();
}

async function openGroupChat(groupId, groupName, memberCount) {
    stopPolling();
    activeChat  = { type: 'group', id: groupId, name: groupName };
    lastMsgTime = null;

    document.getElementById('chat-empty').style.display  = 'none';
    document.getElementById('chat-window').style.display = 'flex';

    const av = document.getElementById('chat-avatar');
    av.innerHTML = '<i class="fas fa-users" style="font-size:16px;"></i>';
    av.className = 'chat-header-avatar group';
    document.getElementById('chat-name').textContent = groupName;
    document.getElementById('chat-sub').textContent  = memberCount + ' members';
    document.getElementById('chat-info-btn').onclick  = () => showGroupInfo(groupId);

    document.getElementById('chat-messages').innerHTML = '';
    highlightActive();
    await fetchMessages();
    startPolling();
}

function highlightActive() {
    document.querySelectorAll('.chat-conv-item').forEach(el => {
        const t  = el.dataset.type;
        const id = parseInt(el.dataset.id, 10);
        el.classList.toggle('active',
            activeChat !== null && activeChat.type === t && activeChat.id === id
        );
    });
}

// ─── Messages ─────────────────────────────────────────────────────────────────
async function fetchMessages() {
    if (!activeChat) return;
    try {
        let url = activeChat.type === 'private'
            ? `${getBase()}/api/chat/private/${activeChat.id}`
            : `${getBase()}/api/chat/groups/${activeChat.id}/messages`;
        if (lastMsgTime) url += `?since=${encodeURIComponent(lastMsgTime)}`;

        const res  = await fetch(url, { headers: authHeaders() });
        const data = await res.json();
        if (data.success && data.messages && data.messages.length) {
            appendMessages(data.messages);
            lastMsgTime = data.messages[data.messages.length - 1].created_at;
        }
    } catch (e) { console.error('fetchMessages:', e); }
}

function appendMessages(msgs) {
    const container  = document.getElementById('chat-messages');
    const atBottom   = container.scrollHeight - container.scrollTop - container.clientHeight < 80;

    msgs.forEach(msg => {
        const isMine  = msg.sender_id === MY_ID;
        const initial = (msg.sender_name || '?').charAt(0).toUpperCase();

        const div = document.createElement('div');
        div.className = `chat-msg ${isMine ? 'mine' : 'other'}`;
        div.innerHTML = `
            ${!isMine ? `<div class="chat-msg-avatar">${initial}</div>` : ''}
            <div class="chat-msg-body">
                ${!isMine && activeChat.type === 'group'
                    ? `<div class="chat-msg-sender">${esc(msg.sender_name)}</div>` : ''}
                <div class="chat-msg-bubble">${esc(msg.text)}</div>
                <div class="chat-msg-time">${fmtMsgTime(msg.created_at)}</div>
            </div>
        `;
        container.appendChild(div);
    });

    if (atBottom || !lastMsgTime) container.scrollTop = container.scrollHeight;
}

// ─── Send ─────────────────────────────────────────────────────────────────────
async function sendMessage() {
    const input = document.getElementById('chat-input');
    const text  = input.value.trim();
    if (!text || !activeChat) return;

    input.value      = '';
    input.style.height = 'auto';

    try {
        const url = activeChat.type === 'private'
            ? `${getBase()}/api/chat/private/${activeChat.id}`
            : `${getBase()}/api/chat/groups/${activeChat.id}/messages`;

        const res  = await fetch(url, {
            method: 'POST', headers: authHeaders(),
            body: JSON.stringify({ text })
        });
        const data = await res.json();
        if (data.success) {
            const msg = data.message;
            msg.sender_name = MY_NAME;
            msg.sender_role = MY_ROLE;
            appendMessages([msg]);
            lastMsgTime = msg.created_at;
            loadInbox();
            loadGroups();
        }
    } catch (e) { console.error('sendMessage:', e); }
}

// ─── Polling ──────────────────────────────────────────────────────────────────
function startPolling() {
    stopPolling();
    pollTimer = setInterval(fetchMessages, 3000);
}
function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

// ─── Input ────────────────────────────────────────────────────────────────────
function setupInput() {
    const input   = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
function setupTabs() {
    document.querySelectorAll('.chat-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.chat-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.chat-tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
        });
    });
}

// ─── Modals ───────────────────────────────────────────────────────────────────
function setupModals() {
    document.getElementById('new-dm-btn').addEventListener('click', openNewDmModal);

    // Live search in DM picker
    document.getElementById('user-search').addEventListener('input', e => {
        renderDmPicker(e.target.value);
    });

    if (MY_ROLE === 'admin') {
        document.getElementById('new-group-btn').addEventListener('click', openCreateGroupModal);
        document.getElementById('group-member-search').addEventListener('input', e => {
            renderGroupMemberPicker(e.target.value);
        });
    }
}

// ── DM picker ──
function openNewDmModal() {
    document.getElementById('user-search').value = '';
    renderDmPicker('');
    openModal('new-dm-modal');
}

function renderDmPicker(query) {
    const container = document.getElementById('user-list');
    const q = query.toLowerCase();
    const filtered = allUsers.filter(u =>
        u.full_name.toLowerCase().includes(q) || u.role.toLowerCase().includes(q)
    );
    if (!filtered.length) {
        container.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-secondary);font-size:13px;">No users found</div>';
        return;
    }
    container.innerHTML = filtered.map(u => `
        <div class="chat-user-item" data-uid="${u.id}" data-name="${esc(u.full_name)}" data-role="${u.role}"
             onclick="selectDmUser(${u.id})">
            <div class="chat-user-item-avatar">${u.full_name.charAt(0).toUpperCase()}</div>
            <div>
                <div class="chat-user-item-name">${esc(u.full_name)}</div>
                <span class="chat-user-item-role role-${u.role}">${u.role.toUpperCase()}</span>
            </div>
        </div>
    `).join('');
}

function selectDmUser(userId) {
    const u = allUsers.find(x => x.id === userId);
    if (!u) return;
    closeModal('new-dm-modal');
    openPrivateChat(u.id, u.full_name, u.role);
}

// ── Group picker ──
function openCreateGroupModal() {
    document.getElementById('group-name').value = '';
    document.getElementById('group-desc').value = '';
    document.getElementById('group-member-search').value = '';
    selectedGroupMembers.clear();
    renderGroupMemberPicker('');
    renderSelectedChips();
    openModal('create-group-modal');
}

function renderGroupMemberPicker(query) {
    const container = document.getElementById('group-member-list');
    const q = query.toLowerCase();
    const filtered = allUsers.filter(u =>
        u.full_name.toLowerCase().includes(q) || u.role.toLowerCase().includes(q)
    );
    if (!filtered.length) {
        container.innerHTML = '<div style="padding:12px;text-align:center;color:var(--text-secondary);font-size:13px;">No users found</div>';
        return;
    }
    container.innerHTML = filtered.map(u => `
        <div class="chat-user-item ${selectedGroupMembers.has(u.id) ? 'selected' : ''}"
             onclick="toggleGroupMember(${u.id})">
            <div class="chat-user-item-avatar">${u.full_name.charAt(0).toUpperCase()}</div>
            <div>
                <div class="chat-user-item-name">${esc(u.full_name)}</div>
                <span class="chat-user-item-role role-${u.role}">${u.role.toUpperCase()}</span>
            </div>
            <div class="chat-user-item-check"><i class="fas fa-check"></i></div>
        </div>
    `).join('');
}

function toggleGroupMember(userId) {
    if (selectedGroupMembers.has(userId)) {
        selectedGroupMembers.delete(userId);
    } else {
        selectedGroupMembers.add(userId);
    }
    renderGroupMemberPicker(document.getElementById('group-member-search').value);
    renderSelectedChips();
}

function renderSelectedChips() {
    const container = document.getElementById('selected-members');
    if (!selectedGroupMembers.size) { container.innerHTML = ''; return; }
    container.innerHTML = [...selectedGroupMembers].map(uid => {
        const u = allUsers.find(x => x.id === uid);
        if (!u) return '';
        return `<div class="chat-member-chip">
            ${esc(u.full_name)}
            <button onclick="toggleGroupMember(${u.id})" title="Remove">&times;</button>
        </div>`;
    }).join('');
}

async function createGroup() {
    const name = document.getElementById('group-name').value.trim();
    const desc = document.getElementById('group-desc').value.trim();
    if (!name) { alert('Group name is required.'); return; }
    if (!selectedGroupMembers.size) { alert('Select at least one member.'); return; }

    try {
        const res  = await fetch(`${getBase()}/api/chat/groups`, {
            method: 'POST', headers: authHeaders(),
            body: JSON.stringify({ name, description: desc, member_ids: [...selectedGroupMembers] })
        });
        const data = await res.json();
        if (data.success) {
            closeModal('create-group-modal');
            await loadGroups();
            document.querySelector('[data-tab="groups"]').click();
            openGroupChat(data.group.id, data.group.name, selectedGroupMembers.size + 1);
        } else {
            alert(data.message || 'Failed to create group.');
        }
    } catch (e) { alert('Network error. Please try again.'); }
}

async function showGroupInfo(groupId) {
    try {
        const res  = await fetch(`${getBase()}/api/chat/groups/${groupId}`, { headers: authHeaders() });
        const data = await res.json();
        if (!data.success) return;
        document.getElementById('ginfo-name').textContent = data.group.name;
        document.getElementById('ginfo-desc').textContent = data.group.description || 'No description.';
        document.getElementById('ginfo-members').innerHTML = (data.members || []).map(m => `
            <div class="ginfo-member-row">
                <div style="width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,#3b82f6,#1e40af);
                     display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff;flex-shrink:0;">
                    ${m.full_name.charAt(0).toUpperCase()}
                </div>
                <div>
                    <div style="font-size:13px;font-weight:600;color:var(--text-primary);">${esc(m.full_name)}</div>
                    <span class="chat-user-item-role role-${m.role}" style="font-size:10px;">${m.role.toUpperCase()}</span>
                </div>
                ${m.id === data.group.created_by
                    ? '<span style="margin-left:auto;font-size:10px;color:var(--accent-blue);font-weight:700;">CREATOR</span>'
                    : ''}
            </div>
        `).join('');
        openModal('group-info-modal');
    } catch (e) { console.error('showGroupInfo:', e); }
}

// ─── Modal helpers ────────────────────────────────────────────────────────────
function openModal(id)  { const el = document.getElementById(id); if (el) el.style.display = 'flex'; }
function closeModal(id) { const el = document.getElementById(id); if (el) el.style.display = 'none'; }
window.addEventListener('click', e => {
    if (e.target.classList.contains('modal')) e.target.style.display = 'none';
});

// ─── Utilities ────────────────────────────────────────────────────────────────
function esc(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function fmtTime(ts) {
    if (!ts) return '';
    try {
        const d    = new Date((ts + '').replace(' ', 'T') + (ts.includes('T') ? '' : 'Z'));
        const diff = Date.now() - d;
        if (diff < 86400000)  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        if (diff < 604800000) return d.toLocaleDateString([], { weekday: 'short' });
        return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch (e) { return ''; }
}

function fmtMsgTime(ts) {
    if (!ts) return '';
    try {
        const d = new Date((ts + '').replace(' ', 'T') + (ts.includes('T') ? '' : 'Z'));
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) { return ''; }
}

// ─── InfraTick Chat (Embedded) ────────────────────────────────────────────────
const AUTH_TOKEN = localStorage.getItem('auth_token');
const MY_ID      = parseInt(localStorage.getItem('user_id'), 10);
const MY_NAME    = localStorage.getItem('user_name') || 'Me';
const MY_ROLE    = localStorage.getItem('user_role') || 'member';

function getBase() { return window.API_BASE || ''; }
function authHeaders() {
    return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${AUTH_TOKEN}` };
}

// ─── State ────────────────────────────────────────────────────────────────────
let allUsers             = [];
let activeChat           = null;
let pollTimer            = null;
let lastMsgTime          = null;
let selectedGroupMembers = new Set();
let chatInitialized      = false;

// ─── Safe element getter ──────────────────────────────────────────────────────
function $id(id) { return document.getElementById(id); }

// ─── Init on DOM ready ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Show admin group button
    const groupBtn = $id('new-group-btn');
    if (groupBtn) {
        groupBtn.style.display = MY_ROLE === 'admin' ? 'flex' : 'none';
    }

    setupTabs();
    setupInput();
    setupModals();

    // Patch the nav item for chat to also call initChat
    // This runs after dashboard.js has already set up nav listeners
    const chatNavItem = document.querySelector('.nav-item[data-view="chat"]');
    if (chatNavItem) {
        chatNavItem.addEventListener('click', () => {
            // Small delay to let dashboard.js show the view first
            setTimeout(initChat, 50);
        });
    }
});

// ─── Called every time the chat view becomes visible ─────────────────────────
async function initChat() {
    if (!AUTH_TOKEN) return;
    await loadUsers();
    await Promise.all([loadInbox(), loadGroups()]);
    chatInitialized = true;
}

// Also listen for dashboardViewChanged as a fallback
window.addEventListener('dashboardViewChanged', async (e) => {
    if (e.detail && e.detail.viewId === 'chat') {
        await initChat();
    }
});

// ─── Load users ───────────────────────────────────────────────────────────────
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
    const list = $id('dm-list');
    if (!list) return;
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
    const list = $id('group-list');
    if (!list) return;
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
    activeChat  = { type: 'private', id: userId, name: userName };
    lastMsgTime = null;

    const empty  = $id('chat-empty');
    const window_ = $id('chat-window');
    if (empty)   empty.style.display   = 'none';
    if (window_) window_.style.display = 'flex';

    const av = $id('chat-avatar');
    if (av) { av.textContent = (userName || '?').charAt(0).toUpperCase(); av.className = 'chat-header-avatar'; }
    const nameEl = $id('chat-name'); if (nameEl) nameEl.textContent = userName;
    const subEl  = $id('chat-sub');  if (subEl)  subEl.textContent  = (userRole || '').charAt(0).toUpperCase() + (userRole || '').slice(1);
    const infoBtn = $id('chat-info-btn'); if (infoBtn) infoBtn.onclick = null;

    const msgs = $id('chat-messages'); if (msgs) msgs.innerHTML = '';
    highlightActive();
    await fetchMessages();
    startPolling();
}

async function openGroupChat(groupId, groupName, memberCount) {
    stopPolling();
    activeChat  = { type: 'group', id: groupId, name: groupName };
    lastMsgTime = null;

    const empty   = $id('chat-empty');
    const window_ = $id('chat-window');
    if (empty)   empty.style.display   = 'none';
    if (window_) window_.style.display = 'flex';

    const av = $id('chat-avatar');
    if (av) { av.innerHTML = '<i class="fas fa-users" style="font-size:16px;"></i>'; av.className = 'chat-header-avatar group'; }
    const nameEl = $id('chat-name'); if (nameEl) nameEl.textContent = groupName;
    const subEl  = $id('chat-sub');  if (subEl)  subEl.textContent  = memberCount + ' members';
    const infoBtn = $id('chat-info-btn'); if (infoBtn) infoBtn.onclick = () => showGroupInfo(groupId);

    const msgs = $id('chat-messages'); if (msgs) msgs.innerHTML = '';
    highlightActive();
    await fetchMessages();
    startPolling();
}

function highlightActive() {
    document.querySelectorAll('.chat-conv-item').forEach(el => {
        const t  = el.dataset.type;
        const id = parseInt(el.dataset.id, 10);
        el.classList.toggle('active', activeChat !== null && activeChat.type === t && activeChat.id === id);
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
    const container = $id('chat-messages');
    if (!container) return;
    const atBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 80;

    msgs.forEach(msg => {
        const isMine  = msg.sender_id === MY_ID;
        const initial = (msg.sender_name || '?').charAt(0).toUpperCase();
        const div = document.createElement('div');
        div.className = `chat-msg ${isMine ? 'mine' : 'other'}`;
        div.innerHTML = `
            ${!isMine ? `<div class="chat-msg-avatar">${initial}</div>` : ''}
            <div class="chat-msg-body">
                ${!isMine && activeChat && activeChat.type === 'group'
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
    const input = $id('chat-input');
    if (!input) return;
    const text = input.value.trim();
    if (!text || !activeChat) return;

    input.value = '';
    input.style.height = 'auto';

    try {
        const url = activeChat.type === 'private'
            ? `${getBase()}/api/chat/private/${activeChat.id}`
            : `${getBase()}/api/chat/groups/${activeChat.id}/messages`;

        const res  = await fetch(url, { method: 'POST', headers: authHeaders(), body: JSON.stringify({ text }) });
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
function startPolling() { stopPolling(); pollTimer = setInterval(fetchMessages, 3000); }
function stopPolling()  { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

// ─── Input ────────────────────────────────────────────────────────────────────
function setupInput() {
    const input   = $id('chat-input');
    const sendBtn = $id('send-btn');
    if (!input || !sendBtn) return;

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
    // Use event delegation on the chat view to avoid issues with hidden elements
    const chatView = $id('chat');
    if (!chatView) return;
    chatView.addEventListener('click', e => {
        const tab = e.target.closest('.chat-tab');
        if (!tab) return;
        chatView.querySelectorAll('.chat-tab').forEach(t => t.classList.remove('active'));
        chatView.querySelectorAll('.chat-tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        const target = $id(`tab-${tab.dataset.tab}`);
        if (target) target.classList.add('active');
    });
}

// ─── Modals ───────────────────────────────────────────────────────────────────
function setupModals() {
    // Use event delegation — buttons may be in hidden views
    document.addEventListener('click', e => {
        if (e.target.closest('#new-dm-btn'))    { openNewDmModal(); return; }
        if (e.target.closest('#new-group-btn')) { if (MY_ROLE === 'admin') openCreateGroupModal(); return; }
    });

    const userSearch = $id('user-search');
    if (userSearch) userSearch.addEventListener('input', e => renderDmPicker(e.target.value));

    const groupSearch = $id('group-member-search');
    if (groupSearch) groupSearch.addEventListener('input', e => renderGroupMemberPicker(e.target.value));

    const manageSearch = $id('manage-member-search');
    if (manageSearch) manageSearch.addEventListener('input', e => renderManagePicker(e.target.value));
}

// ── DM picker ──
function openNewDmModal() {
    if (!allUsers.length) { alert('Loading users... please try again in a moment.'); initChat(); return; }
    const s = $id('user-search'); if (s) s.value = '';
    renderDmPicker('');
    openModal('new-dm-modal');
}

function renderDmPicker(query) {
    const container = $id('user-list');
    if (!container) return;
    const q = query.toLowerCase();
    const filtered = allUsers.filter(u => u.full_name.toLowerCase().includes(q) || u.role.toLowerCase().includes(q));
    if (!filtered.length) {
        container.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-secondary);font-size:13px;">No users found</div>';
        return;
    }
    container.innerHTML = filtered.map(u => `
        <div class="chat-user-item" onclick="selectDmUser(${u.id})">
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

// ── Group create ──
function openCreateGroupModal() {
    if (!allUsers.length) { alert('Loading users... please try again in a moment.'); initChat(); return; }
    const gn = $id('group-name'); if (gn) gn.value = '';
    const gd = $id('group-desc'); if (gd) gd.value = '';
    const gs = $id('group-member-search'); if (gs) gs.value = '';
    selectedGroupMembers.clear();
    renderGroupMemberPicker('');
    renderSelectedChips();
    openModal('create-group-modal');
}

function renderGroupMemberPicker(query) {
    const container = $id('group-member-list');
    if (!container) return;
    const q = query.toLowerCase();
    const filtered = allUsers.filter(u => u.full_name.toLowerCase().includes(q) || u.role.toLowerCase().includes(q));
    container.innerHTML = filtered.map(u => `
        <div class="chat-user-item ${selectedGroupMembers.has(u.id) ? 'selected' : ''}" onclick="toggleGroupMember(${u.id})">
            <div class="chat-user-item-avatar">${u.full_name.charAt(0).toUpperCase()}</div>
            <div>
                <div class="chat-user-item-name">${esc(u.full_name)}</div>
                <span class="chat-user-item-role role-${u.role}">${u.role.toUpperCase()}</span>
            </div>
            <div class="chat-user-item-check"><i class="fas fa-check"></i></div>
        </div>
    `).join('') || '<div style="padding:12px;text-align:center;color:var(--text-secondary);font-size:13px;">No users found</div>';
}

function toggleGroupMember(userId) {
    selectedGroupMembers.has(userId) ? selectedGroupMembers.delete(userId) : selectedGroupMembers.add(userId);
    renderGroupMemberPicker(($id('group-member-search') || {}).value || '');
    renderSelectedChips();
}

function renderSelectedChips() {
    const container = $id('selected-members');
    if (!container) return;
    if (!selectedGroupMembers.size) { container.innerHTML = ''; return; }
    container.innerHTML = [...selectedGroupMembers].map(uid => {
        const u = allUsers.find(x => x.id === uid);
        if (!u) return '';
        return `<div class="chat-member-chip">${esc(u.full_name)}<button onclick="toggleGroupMember(${u.id})" title="Remove">&times;</button></div>`;
    }).join('');
}

async function createGroup() {
    const name = ($id('group-name') || {}).value?.trim();
    const desc = ($id('group-desc') || {}).value?.trim() || '';
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
            // Switch to groups tab
            const groupsTab = document.querySelector('.chat-tab[data-tab="groups"]');
            if (groupsTab) groupsTab.click();
            openGroupChat(data.group.id, data.group.name, selectedGroupMembers.size + 1);
        } else { alert(data.message || 'Failed to create group.'); }
    } catch (e) { alert('Network error. Please try again.'); }
}

// ── Group info ──
async function showGroupInfo(groupId) {
    try {
        const res  = await fetch(`${getBase()}/api/chat/groups/${groupId}`, { headers: authHeaders() });
        const data = await res.json();
        if (!data.success) return;

        const nameEl = $id('ginfo-name'); if (nameEl) nameEl.textContent = data.group.name;
        const descEl = $id('ginfo-desc'); if (descEl) descEl.textContent = data.group.description || 'No description.';

        const manageBtn = $id('ginfo-manage-btn');
        if (manageBtn) manageBtn.style.display = MY_ROLE === 'admin' ? 'flex' : 'none';

        const membersEl = $id('ginfo-members');
        if (membersEl) {
            membersEl.innerHTML = (data.members || []).map(m => `
                <div class="ginfo-member-row">
                    <div style="width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,#3b82f6,#1e40af);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff;flex-shrink:0;">${m.full_name.charAt(0).toUpperCase()}</div>
                    <div>
                        <div style="font-size:13px;font-weight:600;color:var(--text-primary);">${esc(m.full_name)}</div>
                        <span class="chat-user-item-role role-${m.role}" style="font-size:10px;">${m.role.toUpperCase()}</span>
                    </div>
                    ${m.id === data.group.created_by ? '<span style="margin-left:auto;font-size:10px;color:var(--accent-blue);font-weight:700;">CREATOR</span>' : ''}
                </div>
            `).join('');

            // Dissolve button for admins
            const old = $id('ginfo-dissolve-btn'); if (old) old.remove();
            if (MY_ROLE === 'admin') {
                const footer = document.createElement('div');
                footer.id = 'ginfo-dissolve-btn';
                footer.style.cssText = 'margin-top:16px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.06);';
                footer.innerHTML = `<button onclick="openDissolveModal(${groupId}, '${esc(data.group.name)}')"
                    style="width:100%;padding:9px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.2);border-radius:8px;color:#f87171;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;">
                    <i class="fas fa-trash" style="margin-right:6px;"></i>Dissolve Group</button>`;
                membersEl.after(footer);
            }
        }
        openModal('group-info-modal');
    } catch (e) { console.error('showGroupInfo:', e); }
}

// ── Manage members ──
let managingGroupId = null;
let manageSelectedMembers = new Set();

function openManageMembersModal() {
    if (!activeChat || activeChat.type !== 'group') return;
    managingGroupId = activeChat.id;
    manageSelectedMembers = new Set();
    fetch(`${getBase()}/api/chat/groups/${managingGroupId}`, { headers: authHeaders() })
        .then(r => r.json())
        .then(data => {
            if (!data.success) return;
            (data.members || []).forEach(m => { if (m.id !== MY_ID) manageSelectedMembers.add(m.id); });
            const s = $id('manage-member-search'); if (s) s.value = '';
            renderManagePicker('');
            renderManageChips();
            closeModal('group-info-modal');
            openModal('manage-members-modal');
        });
}

function renderManagePicker(query) {
    const container = $id('manage-member-list');
    if (!container) return;
    const q = query.toLowerCase();
    const filtered = allUsers.filter(u => u.full_name.toLowerCase().includes(q) || u.role.toLowerCase().includes(q));
    container.innerHTML = filtered.map(u => `
        <div class="chat-user-item ${manageSelectedMembers.has(u.id) ? 'selected' : ''}" onclick="toggleManageMember(${u.id})">
            <div class="chat-user-item-avatar">${u.full_name.charAt(0).toUpperCase()}</div>
            <div>
                <div class="chat-user-item-name">${esc(u.full_name)}</div>
                <span class="chat-user-item-role role-${u.role}">${u.role.toUpperCase()}</span>
            </div>
            <div class="chat-user-item-check"><i class="fas fa-check"></i></div>
        </div>
    `).join('') || '<div style="padding:12px;text-align:center;color:var(--text-secondary);font-size:13px;">No users found</div>';
}

function toggleManageMember(userId) {
    manageSelectedMembers.has(userId) ? manageSelectedMembers.delete(userId) : manageSelectedMembers.add(userId);
    renderManagePicker(($id('manage-member-search') || {}).value || '');
    renderManageChips();
}

function renderManageChips() {
    const container = $id('manage-selected-members');
    if (!container) return;
    if (!manageSelectedMembers.size) { container.innerHTML = ''; return; }
    container.innerHTML = [...manageSelectedMembers].map(uid => {
        const u = allUsers.find(x => x.id === uid);
        if (!u) return '';
        return `<div class="chat-member-chip">${esc(u.full_name)}<button onclick="toggleManageMember(${u.id})" title="Remove">&times;</button></div>`;
    }).join('');
}

async function saveGroupMembers() {
    if (!managingGroupId) return;
    try {
        const res  = await fetch(`${getBase()}/api/chat/groups/${managingGroupId}/members`, {
            method: 'PUT', headers: authHeaders(),
            body: JSON.stringify({ member_ids: [...manageSelectedMembers] })
        });
        const data = await res.json();
        if (data.success) {
            closeModal('manage-members-modal');
            const sub = $id('chat-sub');
            if (sub) sub.textContent = (manageSelectedMembers.size + 1) + ' members';
            await loadGroups();
        } else { alert(data.message || 'Failed to update members.'); }
    } catch (e) { alert('Network error.'); }
}

// ── Dissolve ──
let dissolveGroupId = null;

function openDissolveModal(groupId, groupName) {
    dissolveGroupId = groupId;
    const el = $id('dissolve-group-name'); if (el) el.textContent = groupName;
    closeModal('group-info-modal');
    openModal('dissolve-group-modal');
}

async function confirmDissolveGroup() {
    if (!dissolveGroupId) return;
    try {
        const res  = await fetch(`${getBase()}/api/chat/groups/${dissolveGroupId}`, { method: 'DELETE', headers: authHeaders() });
        const data = await res.json();
        if (data.success) {
            closeModal('dissolve-group-modal');
            dissolveGroupId = null;
            activeChat = null;
            stopPolling();
            const w = $id('chat-window'); if (w) w.style.display = 'none';
            const e = $id('chat-empty');  if (e) e.style.display  = 'flex';
            await loadGroups();
        } else { alert(data.message || 'Failed to dissolve group.'); }
    } catch (e) { alert('Network error.'); }
}

// ─── Modal helpers ────────────────────────────────────────────────────────────
function openModal(id)  { const el = $id(id); if (el) el.style.display = 'flex'; }
function closeModal(id) { const el = $id(id); if (el) el.style.display = 'none'; }

// ─── Utilities ────────────────────────────────────────────────────────────────
function esc(str) {
    if (str == null) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function fmtTime(ts) {
    if (!ts) return '';
    try {
        const d = new Date((ts+'').replace(' ','T') + ((ts+'').includes('T') ? '' : 'Z'));
        const diff = Date.now() - d;
        if (diff < 86400000)  return d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
        if (diff < 604800000) return d.toLocaleDateString([], {weekday:'short'});
        return d.toLocaleDateString([], {month:'short',day:'numeric'});
    } catch(e) { return ''; }
}

function fmtMsgTime(ts) {
    if (!ts) return '';
    try {
        const d = new Date((ts+'').replace(' ','T') + ((ts+'').includes('T') ? '' : 'Z'));
        return d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
    } catch(e) { return ''; }
}

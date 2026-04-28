// ─── InfraTick Chat — Standalone Page ────────────────────────────────────────
const AUTH_TOKEN = localStorage.getItem('auth_token');
const MY_ID      = parseInt(localStorage.getItem('user_id'), 10);
const MY_NAME    = localStorage.getItem('user_name') || 'Me';
const MY_ROLE    = localStorage.getItem('user_role') || 'member';

if (!AUTH_TOKEN) window.location.href = 'login.html';

function api(path, opts) {
    return fetch((window.API_BASE || '') + path, {
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + AUTH_TOKEN },
        ...opts
    });
}

// ─── State ────────────────────────────────────────────────────────────────────
let allUsers             = [];
let activeChat           = null;
let pollTimer            = null;
let lastMsgTime          = null;
let selectedGroupMembers = new Set();
let managingGroupId      = null;
let manageSelectedMembers = new Set();
let dissolveGroupId      = null;

// ─── Boot ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    // Back button
    const backBtn = document.getElementById('back-btn');
    if (backBtn) backBtn.href = 'dashboard_' + MY_ROLE + '.html';

    // Admin-only group button
    const groupBtn = document.getElementById('new-group-btn');
    if (groupBtn) groupBtn.style.display = MY_ROLE === 'admin' ? 'flex' : 'none';

    // Wire up tabs
    document.querySelectorAll('.chat-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.chat-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.chat-tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            const target = document.getElementById('tab-' + tab.dataset.tab);
            if (target) target.classList.add('active');
        });
    });

    // Wire up send button and Enter key
    const sendBtn = document.getElementById('send-btn');
    const input   = document.getElementById('chat-input');
    if (sendBtn) sendBtn.addEventListener('click', sendMessage);
    if (input) {
        input.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
        });
        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        });
    }

    // Wire up + buttons
    const dmBtn = document.getElementById('new-dm-btn');
    if (dmBtn) dmBtn.addEventListener('click', openNewDmModal);

    if (MY_ROLE === 'admin') {
        if (groupBtn) groupBtn.addEventListener('click', openCreateGroupModal);
        const gms = document.getElementById('group-member-search');
        if (gms) gms.addEventListener('input', e => renderGroupMemberPicker(e.target.value));
        const mms = document.getElementById('manage-member-search');
        if (mms) mms.addEventListener('input', e => renderManagePicker(e.target.value));
    }

    // Search in DM picker
    const us = document.getElementById('user-search');
    if (us) us.addEventListener('input', e => renderDmPicker(e.target.value));

    // Close modals on backdrop click
    document.addEventListener('click', e => {
        if (e.target.classList.contains('modal')) e.target.style.display = 'none';
    });

    // Load data
    await loadAll();
});

async function loadAll() {
    await loadUsers();
    await Promise.all([loadInbox(), loadGroups()]);
}

// ─── Users ────────────────────────────────────────────────────────────────────
async function loadUsers() {
    try {
        const r = await api('/api/chat/users');
        const d = await r.json();
        if (d.success) allUsers = d.users || [];
    } catch(e) { console.error(e); }
}

// ─── Inbox ────────────────────────────────────────────────────────────────────
async function loadInbox() {
    try {
        const r = await api('/api/chat/inbox');
        const d = await r.json();
        renderInbox(d.conversations || []);
    } catch(e) { console.error(e); }
}

function renderInbox(convs) {
    const el = document.getElementById('dm-list');
    if (!el) return;
    if (!convs.length) {
        el.innerHTML = '<div class="chat-list-empty">No conversations yet.<br>Click <b>+</b> to start one.</div>';
        return;
    }
    el.innerHTML = convs.map(c => `
        <div class="chat-conv-item" data-type="private" data-id="${c.other_id}"
             onclick="openPrivateChat(${c.other_id},${JSON.stringify(c.other_name)},${JSON.stringify(c.other_role)})">
            <div class="chat-conv-avatar">${(c.other_name||'?')[0].toUpperCase()}</div>
            <div class="chat-conv-info">
                <div class="chat-conv-name">${esc(c.other_name)}</div>
                <div class="chat-conv-preview">${esc(c.last_text||'')}</div>
            </div>
            <div class="chat-conv-meta">${fmtTime(c.last_at)}</div>
        </div>`).join('');
    markActive();
}

// ─── Groups ───────────────────────────────────────────────────────────────────
async function loadGroups() {
    try {
        const r = await api('/api/chat/groups');
        const d = await r.json();
        renderGroups(d.groups || []);
    } catch(e) { console.error(e); }
}

function renderGroups(groups) {
    const el = document.getElementById('group-list');
    if (!el) return;
    if (!groups.length) {
        el.innerHTML = '<div class="chat-list-empty">No groups yet.' +
            (MY_ROLE === 'admin' ? '<br>Click <b>+</b> to create one.' : '') + '</div>';
        return;
    }
    el.innerHTML = groups.map(g => `
        <div class="chat-conv-item" data-type="group" data-id="${g.id}"
             onclick="openGroupChat(${g.id},${JSON.stringify(g.name)},${g.member_count||0})">
            <div class="chat-conv-avatar group"><i class="fas fa-users" style="font-size:14px;"></i></div>
            <div class="chat-conv-info">
                <div class="chat-conv-name">${esc(g.name)}</div>
                <div class="chat-conv-preview">${g.last_message ? esc(g.last_message) : (g.member_count||0)+' members'}</div>
            </div>
            <div class="chat-conv-meta">${fmtTime(g.last_at||g.created_at)}</div>
        </div>`).join('');
    markActive();
}

// ─── Open chats ───────────────────────────────────────────────────────────────
async function openPrivateChat(userId, userName, userRole) {
    stopPoll();
    activeChat = { type:'private', id:userId, name:userName };
    lastMsgTime = null;

    show('chat-window'); hide('chat-empty');
    setText('chat-name', userName);
    setText('chat-sub', cap(userRole));
    setHtml('chat-avatar', userName[0].toUpperCase());
    setClass('chat-avatar', 'chat-header-avatar');
    const ib = document.getElementById('chat-info-btn'); if (ib) ib.onclick = null;
    setHtml('chat-messages', '');
    markActive();
    await fetchMsgs();
    startPoll();
}

async function openGroupChat(groupId, groupName, memberCount) {
    stopPoll();
    activeChat = { type:'group', id:groupId, name:groupName };
    lastMsgTime = null;

    show('chat-window'); hide('chat-empty');
    setText('chat-name', groupName);
    setText('chat-sub', memberCount + ' members');
    setHtml('chat-avatar', '<i class="fas fa-users" style="font-size:16px;"></i>');
    setClass('chat-avatar', 'chat-header-avatar group');
    const ib = document.getElementById('chat-info-btn'); if (ib) ib.onclick = () => showGroupInfo(groupId);
    setHtml('chat-messages', '');
    markActive();
    await fetchMsgs();
    startPoll();
}

function markActive() {
    document.querySelectorAll('.chat-conv-item').forEach(el => {
        el.classList.toggle('active',
            !!activeChat && activeChat.type === el.dataset.type && activeChat.id === parseInt(el.dataset.id));
    });
}

// ─── Messages ─────────────────────────────────────────────────────────────────
async function fetchMsgs() {
    if (!activeChat) return;
    try {
        let url = activeChat.type === 'private'
            ? '/api/chat/private/' + activeChat.id
            : '/api/chat/groups/' + activeChat.id + '/messages';
        if (lastMsgTime) url += '?since=' + encodeURIComponent(lastMsgTime);
        const r = await api(url);
        const d = await r.json();
        if (d.success && d.messages && d.messages.length) {
            appendMsgs(d.messages);
            lastMsgTime = d.messages[d.messages.length-1].created_at;
        }
    } catch(e) { console.error(e); }
}

function appendMsgs(msgs) {
    const box = document.getElementById('chat-messages');
    if (!box) return;
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    msgs.forEach(msg => {
        const mine = msg.sender_id === MY_ID;
        const div = document.createElement('div');
        div.className = 'chat-msg ' + (mine ? 'mine' : 'other');
        div.innerHTML =
            (!mine ? `<div class="chat-msg-avatar">${(msg.sender_name||'?')[0].toUpperCase()}</div>` : '') +
            `<div class="chat-msg-body">` +
            (!mine && activeChat && activeChat.type==='group' ? `<div class="chat-msg-sender">${esc(msg.sender_name)}</div>` : '') +
            `<div class="chat-msg-bubble">${esc(msg.text)}</div>` +
            `<div class="chat-msg-time">${fmtMsgTime(msg.created_at)}</div>` +
            `</div>`;
        box.appendChild(div);
    });
    if (atBottom || !lastMsgTime) box.scrollTop = box.scrollHeight;
}

// ─── Send ─────────────────────────────────────────────────────────────────────
async function sendMessage() {
    const input = document.getElementById('chat-input');
    if (!input || !activeChat) return;
    const text = input.value.trim();
    if (!text) return;
    input.value = ''; input.style.height = 'auto';
    try {
        const url = activeChat.type === 'private'
            ? '/api/chat/private/' + activeChat.id
            : '/api/chat/groups/' + activeChat.id + '/messages';
        const r = await api(url, { method:'POST', body: JSON.stringify({text}) });
        const d = await r.json();
        if (d.success) {
            d.message.sender_name = MY_NAME;
            appendMsgs([d.message]);
            lastMsgTime = d.message.created_at;
            loadInbox(); loadGroups();
        }
    } catch(e) { console.error(e); }
}

// ─── Poll ─────────────────────────────────────────────────────────────────────
function startPoll() { stopPoll(); pollTimer = setInterval(fetchMsgs, 3000); }
function stopPoll()  { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

// ─── DM Modal ─────────────────────────────────────────────────────────────────
function openNewDmModal() {
    const s = document.getElementById('user-search'); if (s) s.value = '';
    renderDmPicker('');
    openModal('new-dm-modal');
}

function renderDmPicker(q) {
    const box = document.getElementById('user-list'); if (!box) return;
    const filtered = allUsers.filter(u => (u.full_name+u.role).toLowerCase().includes(q.toLowerCase()));
    box.innerHTML = filtered.length
        ? filtered.map(u => `
            <div class="chat-user-item" onclick="selectDm(${u.id})">
                <div class="chat-user-item-avatar">${u.full_name[0].toUpperCase()}</div>
                <div>
                    <div class="chat-user-item-name">${esc(u.full_name)}</div>
                    <span class="chat-user-item-role role-${u.role}">${u.role.toUpperCase()}</span>
                </div>
            </div>`).join('')
        : '<div style="padding:16px;text-align:center;color:var(--text-secondary);">No users found</div>';
}

function selectDm(userId) {
    const u = allUsers.find(x => x.id === userId); if (!u) return;
    closeModal('new-dm-modal');
    openPrivateChat(u.id, u.full_name, u.role);
}

// ─── Group Create Modal ───────────────────────────────────────────────────────
function openCreateGroupModal() {
    ['group-name','group-desc','group-member-search'].forEach(id => { const e = document.getElementById(id); if(e) e.value=''; });
    selectedGroupMembers.clear();
    renderGroupMemberPicker('');
    renderChips('selected-members', selectedGroupMembers, toggleGroupMember);
    openModal('create-group-modal');
}

function renderGroupMemberPicker(q) {
    const box = document.getElementById('group-member-list'); if (!box) return;
    const filtered = allUsers.filter(u => (u.full_name+u.role).toLowerCase().includes(q.toLowerCase()));
    box.innerHTML = filtered.map(u => `
        <div class="chat-user-item ${selectedGroupMembers.has(u.id)?'selected':''}" onclick="toggleGroupMember(${u.id})">
            <div class="chat-user-item-avatar">${u.full_name[0].toUpperCase()}</div>
            <div>
                <div class="chat-user-item-name">${esc(u.full_name)}</div>
                <span class="chat-user-item-role role-${u.role}">${u.role.toUpperCase()}</span>
            </div>
            <div class="chat-user-item-check"><i class="fas fa-check"></i></div>
        </div>`).join('') || '<div style="padding:12px;text-align:center;color:var(--text-secondary);">No users found</div>';
}

function toggleGroupMember(id) {
    selectedGroupMembers.has(id) ? selectedGroupMembers.delete(id) : selectedGroupMembers.add(id);
    const s = document.getElementById('group-member-search');
    renderGroupMemberPicker(s ? s.value : '');
    renderChips('selected-members', selectedGroupMembers, toggleGroupMember);
}

async function createGroup() {
    const name = (document.getElementById('group-name')||{}).value?.trim();
    const desc = (document.getElementById('group-desc')||{}).value?.trim()||'';
    if (!name) { alert('Group name is required.'); return; }
    if (!selectedGroupMembers.size) { alert('Select at least one member.'); return; }
    try {
        const r = await api('/api/chat/groups', { method:'POST', body: JSON.stringify({name, description:desc, member_ids:[...selectedGroupMembers]}) });
        const d = await r.json();
        if (d.success) {
            closeModal('create-group-modal');
            await loadGroups();
            document.querySelector('.chat-tab[data-tab="groups"]')?.click();
            openGroupChat(d.group.id, d.group.name, selectedGroupMembers.size+1);
        } else { alert(d.message||'Failed.'); }
    } catch(e) { alert('Network error.'); }
}

// ─── Group Info Modal ─────────────────────────────────────────────────────────
async function showGroupInfo(groupId) {
    try {
        const r = await api('/api/chat/groups/'+groupId);
        const d = await r.json(); if (!d.success) return;
        setText('ginfo-name', d.group.name);
        setText('ginfo-desc', d.group.description||'No description.');
        const mb = document.getElementById('ginfo-manage-btn');
        if (mb) mb.style.display = MY_ROLE==='admin' ? 'flex' : 'none';
        const me = document.getElementById('ginfo-members');
        if (me) {
            me.innerHTML = (d.members||[]).map(m => `
                <div class="ginfo-member-row">
                    <div style="width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,#3b82f6,#1e40af);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff;flex-shrink:0;">${m.full_name[0].toUpperCase()}</div>
                    <div><div style="font-size:13px;font-weight:600;color:var(--text-primary);">${esc(m.full_name)}</div>
                    <span class="chat-user-item-role role-${m.role}" style="font-size:10px;">${m.role.toUpperCase()}</span></div>
                    ${m.id===d.group.created_by?'<span style="margin-left:auto;font-size:10px;color:var(--accent-blue);font-weight:700;">CREATOR</span>':''}
                </div>`).join('');
            const old = document.getElementById('ginfo-dissolve-btn'); if (old) old.remove();
            if (MY_ROLE==='admin') {
                const f = document.createElement('div'); f.id='ginfo-dissolve-btn';
                f.style.cssText='margin-top:16px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.06);';
                f.innerHTML=`<button onclick="openDissolveModal(${groupId},'${esc(d.group.name)}')" style="width:100%;padding:9px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.2);border-radius:8px;color:#f87171;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;"><i class="fas fa-trash" style="margin-right:6px;"></i>Dissolve Group</button>`;
                me.after(f);
            }
        }
        openModal('group-info-modal');
    } catch(e) { console.error(e); }
}

// ─── Manage Members ───────────────────────────────────────────────────────────
function openManageMembersModal() {
    if (!activeChat||activeChat.type!=='group') return;
    managingGroupId = activeChat.id;
    manageSelectedMembers = new Set();
    api('/api/chat/groups/'+managingGroupId).then(r=>r.json()).then(d => {
        if (!d.success) return;
        (d.members||[]).forEach(m => { if (m.id!==MY_ID) manageSelectedMembers.add(m.id); });
        const s = document.getElementById('manage-member-search'); if (s) s.value='';
        renderManagePicker('');
        renderChips('manage-selected-members', manageSelectedMembers, toggleManageMember);
        closeModal('group-info-modal');
        openModal('manage-members-modal');
    });
}

function renderManagePicker(q) {
    const box = document.getElementById('manage-member-list'); if (!box) return;
    const filtered = allUsers.filter(u => (u.full_name+u.role).toLowerCase().includes(q.toLowerCase()));
    box.innerHTML = filtered.map(u => `
        <div class="chat-user-item ${manageSelectedMembers.has(u.id)?'selected':''}" onclick="toggleManageMember(${u.id})">
            <div class="chat-user-item-avatar">${u.full_name[0].toUpperCase()}</div>
            <div><div class="chat-user-item-name">${esc(u.full_name)}</div>
            <span class="chat-user-item-role role-${u.role}">${u.role.toUpperCase()}</span></div>
            <div class="chat-user-item-check"><i class="fas fa-check"></i></div>
        </div>`).join('') || '<div style="padding:12px;text-align:center;color:var(--text-secondary);">No users found</div>';
}

function toggleManageMember(id) {
    manageSelectedMembers.has(id) ? manageSelectedMembers.delete(id) : manageSelectedMembers.add(id);
    const s = document.getElementById('manage-member-search');
    renderManagePicker(s ? s.value : '');
    renderChips('manage-selected-members', manageSelectedMembers, toggleManageMember);
}

async function saveGroupMembers() {
    if (!managingGroupId) return;
    try {
        const r = await api('/api/chat/groups/'+managingGroupId+'/members', { method:'PUT', body: JSON.stringify({member_ids:[...manageSelectedMembers]}) });
        const d = await r.json();
        if (d.success) { closeModal('manage-members-modal'); await loadGroups(); }
        else { alert(d.message||'Failed.'); }
    } catch(e) { alert('Network error.'); }
}

// ─── Dissolve ─────────────────────────────────────────────────────────────────
function openDissolveModal(groupId, groupName) {
    dissolveGroupId = groupId;
    setText('dissolve-group-name', groupName);
    closeModal('group-info-modal');
    openModal('dissolve-group-modal');
}

async function confirmDissolveGroup() {
    if (!dissolveGroupId) return;
    try {
        const r = await api('/api/chat/groups/'+dissolveGroupId, { method:'DELETE' });
        const d = await r.json();
        if (d.success) {
            closeModal('dissolve-group-modal');
            dissolveGroupId = null; activeChat = null; stopPoll();
            hide('chat-window'); show('chat-empty');
            await loadGroups();
        } else { alert(d.message||'Failed.'); }
    } catch(e) { alert('Network error.'); }
}

// ─── Modals ───────────────────────────────────────────────────────────────────
function openModal(id)  { const e=document.getElementById(id); if(e) e.style.display='flex'; }
function closeModal(id) { const e=document.getElementById(id); if(e) e.style.display='none'; }

// ─── Helpers ──────────────────────────────────────────────────────────────────
function show(id) { const e=document.getElementById(id); if(e) e.style.display='flex'; }
function hide(id) { const e=document.getElementById(id); if(e) e.style.display='none'; }
function setText(id,v) { const e=document.getElementById(id); if(e) e.textContent=v; }
function setHtml(id,v) { const e=document.getElementById(id); if(e) e.innerHTML=v; }
function setClass(id,v){ const e=document.getElementById(id); if(e) e.className=v; }
function cap(s) { return s ? s[0].toUpperCase()+s.slice(1) : ''; }

function renderChips(containerId, memberSet, toggleFn) {
    const box = document.getElementById(containerId); if (!box) return;
    if (!memberSet.size) { box.innerHTML=''; return; }
    box.innerHTML = [...memberSet].map(uid => {
        const u = allUsers.find(x=>x.id===uid); if (!u) return '';
        return `<div class="chat-member-chip">${esc(u.full_name)}<button onclick="${toggleFn.name}(${u.id})" title="Remove">&times;</button></div>`;
    }).join('');
}

function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function fmtTime(ts) {
    if (!ts) return '';
    try {
        const d = new Date(String(ts).replace(' ','T')+(String(ts).includes('T')?'':'Z'));
        const diff = Date.now()-d;
        if (diff<86400000) return d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
        if (diff<604800000) return d.toLocaleDateString([],{weekday:'short'});
        return d.toLocaleDateString([],{month:'short',day:'numeric'});
    } catch(e) { return ''; }
}

function fmtMsgTime(ts) {
    if (!ts) return '';
    try {
        const d = new Date(String(ts).replace(' ','T')+(String(ts).includes('T')?'':'Z'));
        return d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
    } catch(e) { return ''; }
}

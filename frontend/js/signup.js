// ─── Password strength ────────────────────────────────────────────────────────
function checkPasswordStrength(password) {
    const wrap  = document.getElementById('pw-strength-wrap');
    const fill  = document.getElementById('pw-strength-fill');
    const label = document.getElementById('pw-strength-label');
    if (!wrap || !fill || !label) return;

    if (!password) { wrap.style.display = 'none'; return; }
    wrap.style.display = 'flex';

    let score = 0;
    if (password.length >= 8)                              score++;
    if (password.match(/[a-z]/) && password.match(/[A-Z]/)) score++;
    if (password.match(/\d/))                              score++;
    if (password.match(/[^a-zA-Z\d]/))                    score++;

    const levels = [
        { pct: '25%', color: '#ef4444', text: 'Weak' },
        { pct: '50%', color: '#f59e0b', text: 'Fair' },
        { pct: '75%', color: '#3b82f6', text: 'Good' },
        { pct: '100%', color: '#10b981', text: 'Strong' },
    ];
    const lvl = levels[Math.max(0, score - 1)];
    fill.style.width     = lvl.pct;
    fill.style.background = lvl.color;
    label.textContent    = lvl.text;
    label.style.color    = lvl.color;
}

// ─── Eye toggle ───────────────────────────────────────────────────────────────
function toggleSignupPassword() {
    const input = document.getElementById('signup-password');
    const icon  = document.getElementById('signup-eye-icon');
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        if (icon) { icon.classList.remove('fa-eye'); icon.classList.add('fa-eye-slash'); }
    } else {
        input.type = 'password';
        if (icon) { icon.classList.remove('fa-eye-slash'); icon.classList.add('fa-eye'); }
    }
}

// ─── Role selection ───────────────────────────────────────────────────────────
function selectSignupRole(card) {
    document.querySelectorAll('.role-select-card').forEach(c => c.classList.remove('active'));
    card.classList.add('active');
    const roleInput = document.getElementById('signup-role');
    if (roleInput) roleInput.value = card.dataset.role;
}

// ─── Main ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const signupBtn = document.getElementById('signup-submit-btn')
                   || document.querySelector('.login-btn')
                   || document.querySelector('.primary-btn');

    if (!signupBtn) return;

    signupBtn.addEventListener('click', async (e) => {
        e.preventDefault();

        const fullName = (document.getElementById('signup-fullname')?.value || '').trim();
        const email    = (document.getElementById('signup-email')?.value    || '').trim();
        const password =  document.getElementById('signup-password')?.value || '';
        const roleInput = document.getElementById('signup-role');
        const role = roleInput ? roleInput.value : 'member';

        if (!fullName || !email || !password) {
            alert('Please fill out all fields.');
            return;
        }

        if (!role || role === 'Select your role') {
            alert('Please select a role.');
            return;
        }

        const btnSpan = signupBtn.querySelector('span');
        const origText = btnSpan ? btnSpan.textContent : signupBtn.textContent;
        if (btnSpan) btnSpan.textContent = 'Creating account...';
        else signupBtn.textContent = 'Creating account...';
        signupBtn.disabled = true;

        try {
            const response = await fetch(`${window.API_BASE}/api/signup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fullName, email, password, role })
            });

            const data = await response.json();

            if (data.success) {
                alert('Account created! Please sign in.');
                window.location.href = 'login.html';
            } else {
                alert('Signup failed: ' + data.message);
            }
        } catch (err) {
            console.error(err);
            alert('Error connecting to backend.');
        } finally {
            if (btnSpan) btnSpan.textContent = origText;
            else signupBtn.textContent = origText;
            signupBtn.disabled = false;
        }
    });
});

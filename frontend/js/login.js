function togglePassword(inputId) {
  const input = document.getElementById(inputId);
  const icon = input.nextElementSibling;

  if (input.type === "password") {
    input.type = "text";
    icon.style.opacity = "0.5";
  } else {
    input.type = "password";
    icon.style.opacity = "1";
  }
}

// Role selection functionality and clear pre-filled values
document.addEventListener('DOMContentLoaded', function () {
  const roleCards = document.querySelectorAll('.role-card');

  roleCards.forEach(card => {
    card.addEventListener('click', function () {
      roleCards.forEach(c => c.classList.remove('active'));
      this.classList.add('active');
    });
  });

  // Clear login fields on load and after a short delay
  function clearLoginFields() {
    const loginEmail = document.getElementById('login-email');
    const loginPassword = document.getElementById('login-password');
    if (loginEmail) loginEmail.value = '';
    if (loginPassword) loginPassword.value = '';
  }
  clearLoginFields();
  setTimeout(clearLoginFields, 100);
  setTimeout(clearLoginFields, 500);

  // Link Login button to Dashboard via backend API
  const loginBtn = document.querySelector('.login-btn') || document.querySelector('.primary-btn');
  if (loginBtn) {
    loginBtn.addEventListener('click', async () => {
      const emailInput = document.getElementById('login-email');
      const passwordInput = document.getElementById('login-password');
      
      const email = emailInput.value.trim();
      const password = passwordInput.value;
      
      if (!email || !password) {
        alert('Please enter both email and password.');
        return;
      }

      const btnSpan = loginBtn.querySelector('span');
      const origText = btnSpan ? btnSpan.textContent : loginBtn.textContent;
      if (btnSpan) btnSpan.textContent = 'Signing in...';
      else loginBtn.textContent = 'Signing in...';
      loginBtn.disabled = true;

      try {
        const response = await fetch(`${window.API_BASE}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
            localStorage.setItem('auth_token', data.token);
            localStorage.setItem('user_name', data.user.fullName);
            localStorage.setItem('user_email', data.user.email);
            localStorage.setItem('user_role', data.user.role);
            localStorage.setItem('user_id', data.user.id);
            window.location.href = `dashboard_${data.user.role}.html`;
        } else {
            alert('Login failed: ' + data.message);
        }
      } catch (err) {
        console.error(err);
        alert('Error connecting to backend.');
      } finally {
        if (btnSpan) btnSpan.textContent = origText;
        else loginBtn.textContent = origText;
        loginBtn.disabled = false;
      }
    });
  }
});

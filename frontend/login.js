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
  const loginBtn = document.querySelector('.primary-btn');
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

      loginBtn.textContent = 'Authenticating...';
      loginBtn.disabled = true;

      try {
        const response = await fetch('http://127.0.0.1:5000/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Save token if needed, then redirect based on role
            localStorage.setItem('auth_token', data.token);
            window.location.href = `dashboard_${data.role}.html`;
        } else {
            alert('Login failed: ' + data.message);
        }
      } catch (err) {
        console.error(err);
        alert('Error connecting to backend.');
      } finally {
        loginBtn.textContent = 'Login';
        loginBtn.disabled = false;
      }
    });
  }
});

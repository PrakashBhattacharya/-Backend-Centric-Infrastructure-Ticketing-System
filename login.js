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
    const loginEmail = document.querySelector('#login-page input[type="email"]');
    const loginPassword = document.getElementById('login-password');
    if (loginEmail) loginEmail.value = '';
    if (loginPassword) loginPassword.value = '';
  }
  clearLoginFields();
  setTimeout(clearLoginFields, 100);
  setTimeout(clearLoginFields, 500);

  // Link Login button to Dashboard
  const loginBtn = document.querySelector('.primary-btn');
  if (loginBtn) {
    loginBtn.addEventListener('click', () => {
      // Get current active role
      const activeRoleCard = document.querySelector('.role-card.active');
      const role = activeRoleCard ? activeRoleCard.dataset.role : 'member';

      // Redirect based on role
      window.location.href = `dashboard_${role}.html`;
    });
  }
});

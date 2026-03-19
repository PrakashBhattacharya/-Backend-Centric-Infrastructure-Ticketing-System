function checkPasswordStrength(password) {
    const strengthElement = document.querySelector('.password-strength');
    if (!strengthElement) return;

    let strength = 0;
    if (password.length >= 8) strength++;
    if (password.match(/[a-z]/) && password.match(/[A-Z]/)) strength++;
    if (password.match(/\d/)) strength++;
    if (password.match(/[^a-zA-Z\d]/)) strength++;

    if (strength <= 2) {
        strengthElement.textContent = "Weak";
        strengthElement.style.color = "#ef4444";
    } else if (strength === 3) {
        strengthElement.textContent = "Medium";
        strengthElement.style.color = "#f59e0b";
    } else {
        strengthElement.textContent = "Strong";
        strengthElement.style.color = "#10b981";
    }
}

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

document.addEventListener('DOMContentLoaded', () => {
    const signupBtn = document.querySelector('.primary-btn');
    
    if (signupBtn) {
        signupBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            
            // Get values
            const fullName = document.getElementById('signup-fullname').value.trim();
            const email = document.getElementById('signup-email').value.trim();
            const password = document.getElementById('signup-password').value;
            const roleSelect = document.querySelector('select');
            const role = roleSelect.value;
            
            if (!fullName || !email || !password || role === 'Select your role') {
                alert('Please fill out all fields and select a role.');
                return;
            }
            
            signupBtn.textContent = 'Signing up...';
            signupBtn.disabled = true;
            
            try {
                const response = await fetch(`${window.API_BASE}/api/signup`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ fullName, email, password, role })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('Signup successful! Please log in.');
                    window.location.href = 'login.html';
                } else {
                    alert('Signup failed: ' + data.message);
                }
            } catch (err) {
                console.error(err);
                alert('Error connecting to backend.');
            } finally {
                signupBtn.textContent = 'Sign Up →';
                signupBtn.disabled = false;
            }
        });
    }
});

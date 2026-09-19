document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const alertBox = document.getElementById('alert-message');
    const loginBtn = document.getElementById('login-btn');

    function showAlert(message, isSuccess = false) {
        alertBox.textContent = message;
        alertBox.className = `alert-box ${isSuccess ? 'alert-success' : 'alert-error'}`;
        alertBox.style.display = 'block';
    }

    function hideAlert() {
        alertBox.style.display = 'none';
        alertBox.textContent = '';
    }

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const email = document.getElementById('email').value.trim();
        const password = document.getElementById('password').value;
        const role = document.getElementById('role').value;

        if (!email || !password || !role) {
            showAlert('Please fill in all fields.');
            return;
        }

        loginBtn.disabled = true;
        loginBtn.textContent = 'Signing In...';

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    password: password,
                    role: role
                })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                showAlert(data.message || 'Login successful!', true);
                setTimeout(() => {
                    window.location.href = data.redirect_url || '/';
                }, 500);
            } else {
                showAlert(data.message || 'Invalid login credentials.');
            }
        } catch (error) {
            console.error('Login error:', error);
            showAlert('Network error. Unable to log in.');
        } finally {
            loginBtn.disabled = false;
            loginBtn.textContent = 'Sign In';
        }
    });
});

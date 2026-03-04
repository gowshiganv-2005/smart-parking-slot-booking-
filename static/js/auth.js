/**
 * Smart Parking System - Authentication Scripts
 * Handles login, register, and admin login
 */

// ─── UTILITY FUNCTIONS ─────────────────────────────────────

function showAlert(message, type = 'error') {
    const alertBox = document.getElementById('alertBox');
    alertBox.className = `alert alert-${type} show`;
    alertBox.textContent = message;

    if (type === 'success') {
        setTimeout(() => {
            alertBox.classList.remove('show');
        }, 4000);
    }
}

function hideAlert() {
    const alertBox = document.getElementById('alertBox');
    alertBox.classList.remove('show');
}

async function apiRequest(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    const data = await response.json();
    return { ok: response.ok, data };
}


// ─── USER LOGIN ─────────────────────────────────────────────

async function handleLogin() {
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value.trim();
    const btn = document.getElementById('loginBtn');

    if (!email || !password) {
        showAlert('Please fill in all fields');
        return;
    }

    hideAlert();
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Signing In...';

    try {
        const { ok, data } = await apiRequest('/api/login', 'POST', { email, password });

        if (ok) {
            showAlert('Login successful! Redirecting...', 'success');
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 800);
        } else {
            showAlert(data.message || 'Login failed');
            btn.disabled = false;
            btn.textContent = 'Sign In';
        }
    } catch (error) {
        showAlert('Network error. Please try again.');
        btn.disabled = false;
        btn.textContent = 'Sign In';
    }
}


// ─── USER REGISTRATION ─────────────────────────────────────

async function handleRegister() {
    const name = document.getElementById('name').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value.trim();
    const confirmPassword = document.getElementById('confirmPassword').value.trim();
    const btn = document.getElementById('registerBtn');

    if (!name || !email || !password || !confirmPassword) {
        showAlert('Please fill in all fields');
        return;
    }

    if (password.length < 6) {
        showAlert('Password must be at least 6 characters');
        return;
    }

    if (password !== confirmPassword) {
        showAlert('Passwords do not match');
        return;
    }

    hideAlert();
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Creating Account...';

    try {
        const { ok, data } = await apiRequest('/api/register', 'POST', { name, email, password });

        if (ok) {
            showAlert('Account created successfully! Redirecting to login...', 'success');
            setTimeout(() => {
                window.location.href = '/login';
            }, 1500);
        } else {
            showAlert(data.message || 'Registration failed');
            btn.disabled = false;
            btn.textContent = 'Create Account';
        }
    } catch (error) {
        showAlert('Network error. Please try again.');
        btn.disabled = false;
        btn.textContent = 'Create Account';
    }
}


// ─── ADMIN LOGIN ────────────────────────────────────────────

async function handleAdminLogin() {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();
    const btn = document.getElementById('adminLoginBtn');

    if (!username || !password) {
        showAlert('Please fill in all fields');
        return;
    }

    hideAlert();
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Signing In...';

    try {
        const { ok, data } = await apiRequest('/api/admin/login', 'POST', { username, password });

        if (ok) {
            showAlert('Admin login successful! Redirecting...', 'success');
            setTimeout(() => {
                window.location.href = '/admin/dashboard';
            }, 800);
        } else {
            showAlert(data.message || 'Login failed');
            btn.disabled = false;
            btn.textContent = 'Admin Sign In';
        }
    } catch (error) {
        showAlert('Network error. Please try again.');
        btn.disabled = false;
        btn.textContent = 'Admin Sign In';
    }
}


// ─── ENTER KEY HANDLER ──────────────────────────────────────

document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        // Determine which form we're on
        if (document.getElementById('loginForm')) {
            handleLogin();
        } else if (document.getElementById('registerForm')) {
            handleRegister();
        } else if (document.getElementById('adminLoginForm')) {
            handleAdminLogin();
        }
    }
});

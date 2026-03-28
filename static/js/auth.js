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
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout

    try {
        const options = {
            method,
            signal: controller.signal,
        };
        
        if (body instanceof FormData) {
            options.body = body;
            // No Content-Type header for FormData, browser sets it with boundary
        } else if (body) {
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify(body);
        }

        const response = await fetch(url, options);
        clearTimeout(timeoutId);

        let data;
        try {
            data = await response.json();
        } catch (e) {
            throw new Error('Server returned invalid data format');
        }

        return { ok: response.ok, data };
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('Request timed out. Server may be slow, please try again.');
        }
        throw error;
    }
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
            // Store role and superadmin status for UI filtering
            localStorage.setItem('userRole', data.role);
            localStorage.setItem('isSuperAdmin', data.is_super_admin || false);

            setTimeout(() => {
                if (data.role === 'admin' || data.role === 'superadmin') {
                    window.location.href = '/admin/dashboard';
                } else {
                    window.location.href = '/dashboard';
                }
            }, 800);
        } else {
            showAlert(data.message || 'Login failed');
            btn.disabled = false;
            btn.textContent = 'Sign In';
        }
    } catch (error) {
        console.error('Login error:', error);
        showAlert(error.message || 'Network error. Please try again.');
        btn.disabled = false;
        btn.textContent = 'Sign In';
    }
}


// ─── USER REGISTRATION ─────────────────────────────────────

async function handleRegister() {
    const name = document.getElementById('name').value.trim();
    const email = document.getElementById('email').value.trim();
    const phone = document.getElementById('phone').value.trim();
    const plateNumber = document.getElementById('plateNumber').value.trim();
    const vehiclePapers = document.getElementById('vehiclePapers').files[0];
    const driverLicense = document.getElementById('driverLicense').files[0];
    const role = document.getElementById('role').value;
    const password = document.getElementById('password').value.trim();
    const confirmPassword = document.getElementById('confirmPassword').value.trim();
    const btn = document.getElementById('registerBtn');

    if (!name || !email || !phone || !plateNumber || !role || !password || !confirmPassword || !vehiclePapers || !driverLicense) {
        showAlert('Please fill in all fields and upload required documents');
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
        const formData = new FormData();
        formData.append('name', name);
        formData.append('email', email);
        formData.append('phone', phone);
        formData.append('plate_number', plateNumber);
        formData.append('vehicle_papers', vehiclePapers);
        formData.append('driver_license', driverLicense);
        formData.append('password', password);
        formData.append('role', role);

        const { ok, data } = await apiRequest('/api/register', 'POST', formData);

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
        console.error('Registration error:', error);
        showAlert(error.message || 'Network error. Please try again.');
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
        console.error('Admin login error:', error);
        showAlert(error.message || 'Network error. Please try again.');
        btn.disabled = false;
        btn.textContent = 'Admin Sign In';
    }
}


// ─── ENTER KEY HANDLER ──────────────────────────────────────

document.addEventListener('keydown', function (e) {
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

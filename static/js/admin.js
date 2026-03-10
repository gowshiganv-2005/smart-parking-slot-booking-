/**
 * Smart Parking System - Admin Dashboard Scripts
 * Handles slot management, bookings, users, and real-time updates
 */

// ─── STATE ──────────────────────────────────────────────────

let currentCancelBookingId = null;
let currentDeleteSlotId = null;
let refreshInterval = null;


// ─── UTILITY FUNCTIONS ──────────────────────────────────────

async function apiRequest(url, method = 'GET', body = null) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout for admin calls

    try {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' },
            signal: controller.signal,
        };
        if (body) options.body = JSON.stringify(body);

        const response = await fetch(url, options);
        clearTimeout(timeoutId);
        const data = await response.json();
        return { ok: response.ok, data };
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            console.error('Request timed out:', url);
            showToast('Request timed out. Server or Google Sheets may be slow.', 'error');
        } else {
            console.error('API Request Error:', error);
            showToast('Dashboard fetching issue. Check connection.', 'error');
        }
        return { ok: false, data: { message: error.message } };
    }
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || '✅'}</span>
        <span class="toast-message">${message}</span>
    `;

    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}


const isSuperAdmin = localStorage.getItem('isSuperAdmin') === 'true';

function switchTab(tabId) {
    if (!isSuperAdmin && ['users', 'logs', 'slots'].includes(tabId)) {
        showToast('Access denied: Requires Super Admin', 'error');
        return;
    }

    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    document.getElementById(`nav-${tabId}`).classList.add('active');

    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-${tabId}`).classList.add('active');

    document.getElementById('sidebar').classList.remove('open');

    if (tabId === 'overview') loadDashboard();
    else if (tabId === 'slots') loadManageSlots();
    else if (tabId === 'bookings') loadAllBookings();
    else if (tabId === 'users') loadUsers();
    else if (tabId === 'logs') loadLogs();
}


// ─── LOAD DASHBOARD ─────────────────────────────────────────

async function loadDashboard(silent = false) {
    try {
        const { ok, data } = await apiRequest('/api/admin/dashboard-data', 'GET', null, silent);

        if (ok) {
            // Render stats
            const s = data.stats;
            document.getElementById('totalSlots').textContent = s.total_slots;
            document.getElementById('availableSlots').textContent = s.available_slots;
            document.getElementById('bookedSlots').textContent = s.booked_slots;
            document.getElementById('totalUsers').textContent = s.total_users;
            if (document.getElementById('parkedVehicles')) {
                document.getElementById('parkedVehicles').textContent = s.parked_vehicles || 0;
            }

            // Render slots
            renderDashSlotMap(data.slots);

            // Render bookings and vehicles
            const allBookings = data.bookings;
            const activeVehicles = allBookings.filter(b => b.UserStatus === 'Logged In');

            // Render active vehicles
            renderActiveVehicles(activeVehicles);

            // Render recent bookings (last 5)
            renderRecentBookings(allBookings.slice(-5).reverse());
        } else {
            const errorMsg = data.error || data.message || 'Fetching issue';
            showToast(`Dashboard Error: ${errorMsg}`, 'error');
            console.error('Dashboard Fetch failed:', data);

            // Auto-retry once after 3 seconds
            setTimeout(() => {
                const activeTab = document.querySelector('.tab-content.active');
                if (activeTab && activeTab.id === 'tab-overview') {
                    console.log('Auto-retrying dashboard fetch...');
                    loadDashboard();
                }
            }, 3000);
        }
    } catch (e) {
        console.error('Failed to load dashboard', e);
        showToast('Connection failed. Retrying...', 'info');
    }
}

function renderActiveVehicles(activeVehicles) {
    const container = document.getElementById('activeParkedTable');
    const countBadge = document.getElementById('activeVehicleCount');

    countBadge.textContent = `${activeVehicles.length} Parked`;

    if (!activeVehicles.length) {
        container.innerHTML = `
            <div class="empty-state" style="padding: 20px;">
                <p style="color: var(--text-muted); font-size: 14px;">No vehicles currently parked</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Vehicle/User</th>
                    <th>Slot</th>
                    <th>Check-in Time</th>
                </tr>
            </thead>
            <tbody>
                ${activeVehicles.map(v => `
                    <tr>
                        <td>
                            <div style="font-weight: 600;">${v.UserName}</div>
                            <div style="font-size: 11px; opacity: 0.6;">${v.UserEmail}</div>
                        </td>
                        <td><span class="status-badge status-booked">${v.SlotNumber}</span></td>
                        <td style="font-family: monospace; font-size: 12px; color: var(--accent-green);">${v.LoginTime}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}


// ─── RENDER DASHBOARD SLOT MAP ──────────────────────────────

function renderDashSlotMap(slots) {
    const container = document.getElementById('dashSlotMap');
    if (!slots.length) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">🅿️</div><h3>No Slots</h3></div>';
        return;
    }

    container.innerHTML = slots.map(slot => `
        <div class="slot-card ${slot.Status.toLowerCase()}" style="cursor: default;">
            <div class="slot-icon">${slot.Status === 'Available' ? '🚗' : '🔒'}</div>
            <div class="slot-number">${slot.SlotNumber}</div>
            <span class="slot-status">${slot.Status}</span>
        </div>
    `).join('');
}


// ─── RENDER RECENT BOOKINGS ─────────────────────────────────

function renderRecentBookings(bookings) {
    const container = document.getElementById('recentBookingsTable');
    if (!bookings.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📋</div>
                <h3>No Bookings Yet</h3>
                <p>No bookings have been made</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>User</th>
                    <th>Slot</th>
                    <th>Date</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                ${bookings.map(b => `
                    <tr>
                        <td>#${b.BookingID}</td>
                        <td>${b.UserName}</td>
                        <td><span class="status-badge status-booked">${b.SlotNumber}</span></td>
                        <td>${b.Date}</td>
                        <td>
                            <span class="access-badge badge-${(b.UserStatus || 'Pending').toLowerCase().replace(' ', '-')}">
                                ${b.UserStatus || 'Pending'}
                            </span>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}


// ─── MANAGE SLOTS ───────────────────────────────────────────

async function loadManageSlots() {
    try {
        const { ok, data } = await apiRequest('/api/admin/slots');
        if (ok) {
            renderManageSlots(data.slots);
        } else {
            showToast('Failed to load slots data', 'error');
            document.getElementById('manageSlots').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Failed to load slots</h3></div>';
        }
    } catch (e) {
        console.error('Failed to load slots', e);
        document.getElementById('manageSlots').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Failed to load slots</h3></div>';
    }
}

function renderManageSlots(slots) {
    const container = document.getElementById('manageSlots');
    if (!slots.length) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">🅿️</div><h3>No Slots</h3><p>Add a new slot above</p></div>';
        return;
    }

    container.innerHTML = slots.map(slot => `
        <div class="manage-slot-card">
            <div class="slot-icon" style="font-size: 28px; margin-bottom: 8px;">
                ${slot.Status === 'Available' ? '🚗' : '🔒'}
            </div>
            <div class="slot-number" style="font-size: 16px; font-weight: 700; margin-bottom: 6px;">
                ${slot.SlotNumber}
            </div>
            <span class="status-badge ${slot.Status === 'Available' ? 'status-available' : slot.Status === 'Booked' ? 'status-booked' : 'status-warning'}">
                ${slot.Status}
            </span>
            <div class="slot-actions">
                ${slot.Status === 'Available' ? `
                    <div style="display: flex; gap: 4px; justify-content: center; width: 100%;">
                        <button class="btn btn-outline btn-sm" onclick="updateSlotStatus(${slot.SlotID}, 'Maintenance')" style="padding: 4px 8px; font-size: 11px;">
                            🛠️ Fix
                        </button>
                        <button class="btn btn-danger btn-sm" onclick="openDeleteModal(${slot.SlotID})" style="padding: 4px 8px; font-size: 11px;">
                            🗑️
                        </button>
                    </div>
                ` : slot.Status === 'Maintenance' ? `
                    <div style="display: flex; gap: 4px; justify-content: center; width: 100%;">
                        <button class="btn btn-success btn-sm" onclick="updateSlotStatus(${slot.SlotID}, 'Available')" style="padding: 4px 8px; font-size: 11px;">
                            ✅ Ready
                        </button>
                        <button class="btn btn-danger btn-sm" onclick="openDeleteModal(${slot.SlotID})" style="padding: 4px 8px; font-size: 11px;">
                            🗑️
                        </button>
                    </div>
                ` : `
                    <button class="btn btn-outline btn-sm" disabled style="width: 100%; opacity: 0.6; font-size: 11px;">
                        🔒 Occupied
                    </button>
                `}
            </div>
        </div>
    `).join('');
}

async function updateSlotStatus(slotId, status) {
    try {
        const { ok, data } = await apiRequest('/api/admin/slots/update', 'POST', { slot_id: slotId, status });

        if (ok) {
            showToast(data.message, 'success');
            loadManageSlots();
            loadDashboard();
        } else {
            showToast(data.message || 'Update failed', 'error');
        }
    } catch (e) {
        showToast('Network error', 'error');
    }
}


// ─── ADD SLOT ───────────────────────────────────────────────

async function addSlot() {
    const input = document.getElementById('newSlotNumber');
    const slotNumber = input.value.trim();

    if (!slotNumber) {
        showToast('Please enter a slot number', 'error');
        return;
    }

    try {
        const { ok, data } = await apiRequest('/api/admin/slots/add', 'POST', { slot_number: slotNumber });

        if (ok) {
            showToast(`Slot ${slotNumber} added successfully!`, 'success');
            input.value = '';
            loadManageSlots();
            loadDashboard();
        } else {
            showToast(data.message || 'Failed to add slot', 'error');
        }
    } catch (e) {
        showToast('Network error', 'error');
    }
}


// ─── DELETE SLOT ────────────────────────────────────────────

function openDeleteModal(slotId) {
    currentDeleteSlotId = slotId;
    document.getElementById('deleteModal').classList.add('show');
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('show');
    currentDeleteSlotId = null;
}

async function confirmDeleteSlot() {
    if (!currentDeleteSlotId) return;

    const btn = document.getElementById('confirmDeleteBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Deleting...';

    try {
        const { ok, data } = await apiRequest('/api/admin/slots/delete', 'POST', { slot_id: currentDeleteSlotId });

        if (ok) {
            showToast('Slot deleted successfully', 'success');
            closeDeleteModal();
            loadManageSlots();
            loadDashboard();
        } else {
            showToast(data.message || 'Failed to delete slot', 'error');
        }
    } catch (e) {
        showToast('Network error', 'error');
    }

    btn.disabled = false;
    btn.textContent = 'Delete Slot';
}


// ─── ALL BOOKINGS ───────────────────────────────────────────

async function loadAllBookings() {
    try {
        const { ok, data } = await apiRequest('/api/admin/bookings');
        if (ok) {
            renderAllBookings(data.bookings);
        } else {
            showToast('Failed to load bookings', 'error');
            document.getElementById('allBookingsTable').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Failed to load bookings</h3></div>';
        }
    } catch (e) {
        console.error('Failed to load bookings', e);
        document.getElementById('allBookingsTable').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Failed to load bookings</h3></div>';
    }
}

function renderAllBookings(bookings) {
    const container = document.getElementById('allBookingsTable');
    if (!bookings.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📋</div>
                <h3>No Bookings</h3>
                <p>No bookings have been made yet</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>User</th>
                    <th>Slot</th>
                    <th>Date/Time</th>
                    <th>Status</th>
                    <th>Login/Logout</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${bookings.map(b => `
                    <tr>
                        <td title="Booking ID #${b.BookingID}">#${b.BookingID}</td>
                        <td>
                            <div style="font-weight: 600;">${b.UserName}</div>
                            <div style="font-size: 11px; opacity: 0.6;">${b.UserEmail}</div>
                        </td>
                        <td><span class="status-badge status-booked">${b.SlotNumber}</span></td>
                        <td>
                            <div style="font-size: 13px;">${b.Date}</div>
                            <div style="font-size: 11px; opacity: 0.6;">${b.Time}</div>
                        </td>
                        <td>
                            <span class="access-badge badge-${(b.UserStatus || 'Pending').toLowerCase().replace(' ', '-')}">
                                ${b.UserStatus || 'Pending'}
                            </span>
                        </td>
                        <td>
                            <div style="font-size: 11px;">In: ${b.LoginTime || 'N/A'}</div>
                            <div style="font-size: 11px;">Out: ${b.LogoutTime || 'N/A'}</div>
                        </td>
                        <td>
                            <button class="btn btn-danger btn-sm" onclick="openCancelModal(${b.BookingID})" style="padding: 4px 8px; font-size: 11px;">
                                Cancel
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}


// ─── CANCEL BOOKING (ADMIN) ─────────────────────────────────

function openCancelModal(bookingId) {
    currentCancelBookingId = bookingId;
    document.getElementById('cancelModal').classList.add('show');
}

function closeCancelModal() {
    document.getElementById('cancelModal').classList.remove('show');
    currentCancelBookingId = null;
}

async function confirmCancelBooking() {
    if (!currentCancelBookingId) return;

    const btn = document.getElementById('confirmCancelBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Cancelling...';

    try {
        const { ok, data } = await apiRequest('/api/admin/bookings/cancel', 'POST', { booking_id: currentCancelBookingId });

        if (ok) {
            showToast('Booking cancelled. User has been notified.', 'info');
            closeCancelModal();
            loadAllBookings();
            loadDashboard();
        } else {
            showToast(data.message || 'Failed to cancel booking', 'error');
        }
    } catch (e) {
        showToast('Network error', 'error');
    }

    btn.disabled = false;
    btn.textContent = 'Cancel Booking';
}


// ─── USERS TABLE ────────────────────────────────────────────

async function loadUsers() {
    try {
        const { ok, data } = await apiRequest('/api/admin/users');
        if (ok) {
            renderUsersTable(data.users);
        } else {
            showToast('Failed to load users', 'error');
            document.getElementById('usersTable').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Failed to load users</h3></div>';
        }
    } catch (e) {
        console.error('Failed to load users', e);
        document.getElementById('usersTable').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Failed to load users</h3></div>';
    }
}

function renderUsersTable(users) {
    const container = document.getElementById('usersTable');
    if (!users.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">👥</div>
                <h3>No Users</h3>
                <p>No users have registered yet</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>User ID</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Phone</th>
                    <th>Last Active</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${users.map(u => `
                    <tr>
                        <td>#${u.UserID}</td>
                        <td>${u.Name}</td>
                        <td>${u.Email}</td>
                        <td>${u.Phone || 'N/A'}</td>
                        <td>
                            <span style="font-size: 11px; color: ${u.LastActive && u.LastActive !== 'N/A' ? 'var(--accent-green)' : 'var(--text-muted)'};">
                                ${u.LastActive || 'N/A'}
                            </span>
                        </td>
                        <td>
                            ${u.UserID !== '0' ? `
                                <button class="btn btn-danger btn-sm" onclick="deleteUser('${u.UserID}')" title="Delete User">
                                    🗑️
                                </button>
                            ` : '<span class="badge badge-available">System</span>'}
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}


// ─── ACTIVITY LOGS ──────────────────────────────────────────

async function loadLogs() {
    try {
        const { ok, data } = await apiRequest('/api/admin/logs');
        if (ok) {
            renderLogsTable(data.logs);
        } else {
            showToast('Failed to load logs', 'error');
            document.getElementById('logsTable').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Failed to load logs</h3></div>';
        }
    } catch (e) {
        console.error('Failed to load logs', e);
        document.getElementById('logsTable').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Failed to load logs</h3></div>';
    }
}

function renderLogsTable(logs) {
    const container = document.getElementById('logsTable');
    if (!logs.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📜</div>
                <h3>No Logs</h3>
                <p>No activity has been recorded yet</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>User</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${logs.map(log => `
                    <tr>
                        <td>
                            <div style="font-weight: 600;">${log.Time}</div>
                            <div style="font-size: 11px; color: var(--text-muted);">${log.Date}</div>
                        </td>
                        <td>
                            <div style="font-weight: 600;">${log.UserName}</div>
                            <div style="font-size: 11px; color: var(--text-muted);">${log.UserEmail}</div>
                        </td>
                        <td>
                            <span class="status-badge ${log.Action.includes('Login') ? 'status-available' : log.Action.includes('Booked') ? 'status-booked' : ''}">
                                ${log.Action}
                            </span>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}


// ─── LOGOUT ─────────────────────────────────────────────────

async function handleLogout() {
    try {
        await apiRequest('/api/logout', 'POST');
        window.location.href = '/admin';
    } catch (e) {
        window.location.href = '/admin';
    }
}


// ─── QR CODE SCANNER ────────────────────────────────────────

let html5QrCodeScanner = null;
let scannerRunning = false;

function startScanner() {
    if (scannerRunning) return;

    html5QrCodeScanner = new Html5Qrcode("qr-reader");

    html5QrCodeScanner.start(
        { facingMode: "environment" },
        {
            fps: 10,
            qrbox: { width: 250, height: 250 }
        },
        onScanSuccess,
        onScanFailure
    ).then(() => {
        scannerRunning = true;
        document.getElementById('startScanBtn').style.display = 'none';
        document.getElementById('stopScanBtn').style.display = 'inline-flex';
        showToast('Camera started. Point at a QR code.', 'info');
    }).catch(err => {
        console.error('Scanner error:', err);
        showToast('Failed to access camera. Please allow camera permissions.', 'error');
    });
}

function stopScanner() {
    if (html5QrCodeScanner && scannerRunning) {
        html5QrCodeScanner.stop().then(() => {
            scannerRunning = false;
            document.getElementById('startScanBtn').style.display = 'inline-flex';
            document.getElementById('stopScanBtn').style.display = 'none';
            html5QrCodeScanner.clear();
        }).catch(err => {
            console.error('Stop scanner error:', err);
        });
    }
}

function onScanSuccess(decodedText, decodedResult) {
    // Stop scanner after successful scan
    stopScanner();

    // Play a beep sound effect
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(880, audioCtx.currentTime);
        oscillator.connect(audioCtx.destination);
        oscillator.start();
        oscillator.stop(audioCtx.currentTime + 0.15);
    } catch (e) { }

    // Verify the scanned QR code
    verifyQrCode(decodedText);
}

function onScanFailure(error) {
    // Silently ignore scan failures (happens every frame without a QR code)
}

async function verifyQrCode(qrData) {
    const resultContainer = document.getElementById('scanResultContainer');
    resultContainer.innerHTML = `
        <div class="loading-overlay" style="padding: 40px;">
            <div class="spinner"></div>
            <p>Verifying booking...</p>
        </div>
    `;

    try {
        const { ok, data } = await apiRequest('/api/admin/verify-booking', 'POST', { qr_data: qrData });

        if (ok && data.verified) {
            const b = data.booking;
            resultContainer.innerHTML = `
                <div style="text-align: center; padding: 20px;">
                    <div style="width: 64px; height: 64px; background: rgba(34, 197, 94, 0.15); border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 32px; margin-bottom: 16px;">✅</div>
                    <h3 style="color: var(--accent-green); font-size: 20px; margin-bottom: 4px;">Booking Verified!</h3>
                    <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 20px;">Active booking found in the system</p>
                    
                    <div style="background: rgba(34, 197, 94, 0.08); border: 1px solid rgba(34, 197, 94, 0.2); border-radius: 12px; padding: 20px; text-align: left;">
                        <div style="display: grid; grid-template-columns: auto 1fr; gap: 12px 16px; font-size: 14px;">
                            <span style="color: var(--text-muted); font-weight: 600;">Booking ID:</span>
                            <span style="font-weight: 700;">#${b.BookingID}</span>
                            
                            <span style="color: var(--text-muted); font-weight: 600;">User:</span>
                            <span style="font-weight: 700;">${b.UserName}</span>
                            
                            <span style="color: var(--text-muted); font-weight: 600;">Email:</span>
                            <span>${b.UserEmail}</span>
                            
                            <span style="color: var(--text-muted); font-weight: 600;">Slot:</span>
                            <span><span class="status-badge status-booked">${b.SlotNumber}</span></span>
                            
                            <span style="color: var(--text-muted); font-weight: 600;">Date:</span>
                            <span>${b.Date}</span>
                            
                            <span style="color: var(--text-muted); font-weight: 600;">Time:</span>
                            <span>${b.Time}</span>
                        </div>
                        <div style="margin-top: 20px;">
                            <a href="/parking-access?booking_id=${b.BookingID}" target="_blank" class="btn btn-outline" style="width: 100%;">
                                Open Verification Page
                            </a>
                        </div>
                    </div>
                </div>
            `;
        } else if (ok && !data.verified) {
            resultContainer.innerHTML = `
                <div style="text-align: center; padding: 20px;">
                    <div style="width: 64px; height: 64px; background: rgba(249, 115, 22, 0.15); border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 32px; margin-bottom: 16px;">⚠️</div>
                    <h3 style="color: var(--accent-orange); font-size: 20px; margin-bottom: 4px;">Booking Not Active</h3>
                    <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 16px;">${data.message}</p>
                    ${data.qr_info ? `
                        <div style="background: rgba(249, 115, 22, 0.08); border: 1px solid rgba(249, 115, 22, 0.2); border-radius: 12px; padding: 16px; text-align: left; font-size: 13px;">
                            <p><strong>QR Info:</strong> ${data.qr_info.user_name} — Slot ${data.qr_info.slot_number}</p>
                        </div>
                    ` : ''}
                </div>
            `;
        } else {
            resultContainer.innerHTML = `
                <div style="text-align: center; padding: 20px;">
                    <div style="width: 64px; height: 64px; background: rgba(239, 68, 68, 0.15); border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 32px; margin-bottom: 16px;">❌</div>
                    <h3 style="color: var(--accent-red); font-size: 20px; margin-bottom: 4px;">Invalid QR Code</h3>
                    <p style="color: var(--text-muted); font-size: 13px;">${data.message || 'This QR code is not from the Smart Parking system.'}</p>
                </div>
            `;
        }
    } catch (e) {
        resultContainer.innerHTML = `
            <div style="text-align: center; padding: 20px;">
                <div style="width: 64px; height: 64px; background: rgba(239, 68, 68, 0.15); border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 32px; margin-bottom: 16px;">❌</div>
                <h3 style="color: var(--accent-red); font-size: 20px; margin-bottom: 4px;">Verification Error</h3>
                <p style="color: var(--text-muted); font-size: 13px;">Network error occurred during verification.</p>
            </div>
        `;
    }
}

function verifyManualQr() {
    const input = document.getElementById('manualQrInput');
    const qrData = input.value.trim();
    if (!qrData) {
        showToast('Please paste QR code data', 'error');
        return;
    }
    verifyQrCode(qrData);
}

function closeVerifyModal() {
    document.getElementById('verifyModal').classList.remove('show');
}


// ─── REAL-TIME UPDATES ──────────────────────────────────────

function startAutoRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = setInterval(() => {
        const activeTab = document.querySelector('.tab-content.active');
        if (activeTab) {
            const id = activeTab.id;
            if (id === 'tab-overview') loadDashboard(true);
        }
    }, 120000); // 2 minutes — prevents Google Sheets API quota errors
}


// ─── ENTER KEY FOR ADD SLOT ─────────────────────────────────

document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && document.activeElement.id === 'newSlotNumber') {
        addSlot();
    }
    if (e.key === 'Enter' && document.activeElement.id === 'manualQrInput') {
        verifyManualQr();
    }
});


// ─── INITIALIZATION ─────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    // Hide SuperAdmin tabs for regular admins
    if (!isSuperAdmin) {
        if (document.getElementById('nav-users')) document.getElementById('nav-users').style.display = 'none';
        if (document.getElementById('nav-logs')) document.getElementById('nav-logs').style.display = 'none';
        if (document.getElementById('nav-slots')) document.getElementById('nav-slots').style.display = 'none';
    }

    loadDashboard();
    startAutoRefresh();
});

async function deleteUser(userId) {
    if (!confirm('Are you sure you want to delete this user? This will also remove their bookings.')) return;

    const { ok, data } = await apiRequest('/api/admin/users/delete', 'POST', { user_id: userId });
    if (ok) {
        showToast('User deleted successfully', 'success');
        loadUsers();
    } else {
        showToast(data.message || 'Failed to delete user', 'error');
    }
}

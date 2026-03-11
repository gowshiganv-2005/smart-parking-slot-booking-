/**
 * Smart Parking System - User Dashboard Scripts
 * Handles slot viewing, booking, cancellation, and real-time updates
 */

// ─── STATE ──────────────────────────────────────────────────

let currentSlotId = null;
let currentBookingId = null;
let refreshInterval = null;


// ─── UTILITY FUNCTIONS ──────────────────────────────────────

async function apiRequest(url, method = 'GET', body = null, silent = false) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout

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
        if (!silent) {
            if (error.name === 'AbortError') {
                console.error('Request timed out:', url);
                showToast('Request timed out. Please refresh the page.', 'error');
            } else {
                console.error('API Request Error:', error);
                showToast('Connection issue. Please check your network.', 'error');
            }
        } else {
            console.warn('Background refresh failed (silent):', url);
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


// ─── TAB NAVIGATION ─────────────────────────────────────────

function switchTab(tab) {
    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    document.getElementById(`nav-${tab}`).classList.add('active');

    // Update content
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');

    // Close mobile sidebar
    document.getElementById('sidebar').classList.remove('open');

    // Load data for the tab
    if (tab === 'overview') loadOverview();
    else if (tab === 'slots') loadAllSlots();
    else if (tab === 'bookings') loadMyBookings();
    else if (tab === 'feedback') {
        // Feedback tab - no data loading needed as it's static
    }
}


// ─── LOAD USER INFO ─────────────────────────────────────────

async function loadUserInfo() {
    try {
        const { ok, data } = await apiRequest('/api/user/info');
        if (ok) {
            const user = data.user;
            document.getElementById('userName').textContent = user.Name;
            document.getElementById('userEmail').textContent = user.Email;
            document.getElementById('userPhone').textContent = user.Phone || 'N/A';
            document.getElementById('welcomeName').textContent = user.Name.split(' ')[0];
            document.getElementById('userAvatar').textContent = user.Name.charAt(0).toUpperCase();
        }
    } catch (e) {
        console.error('Failed to load user info', e);
    }
}


// ─── LOAD OVERVIEW ──────────────────────────────────────────

async function loadOverview(silent = false) {
    try {
        const [slotsRes, bookingsRes] = await Promise.all([
            apiRequest('/api/slots', 'GET', null, silent),
            apiRequest('/api/user/bookings', 'GET', null, silent)
        ]);

        if (slotsRes.ok) {
            const slots = slotsRes.data.slots;
            const available = slots.filter(s => s.Status === 'Available').length;
            const booked = slots.filter(s => s.Status === 'Booked').length;

            document.getElementById('availableCount').textContent = available;
            document.getElementById('bookedCount').textContent = booked;
            document.getElementById('totalCount').textContent = slots.length;
            document.getElementById('quickAvail').textContent = available;

            renderSlotGrid('overviewSlots', slots);
        }

        if (bookingsRes.ok) {
            document.getElementById('myBookingsCount').textContent = bookingsRes.data.bookings.length;
        }
    } catch (e) {
        console.error('Failed to load overview', e);
    }
}


// ─── LOAD ALL SLOTS ─────────────────────────────────────────

async function loadAllSlots(silent = false) {
    try {
        const { ok, data } = await apiRequest('/api/slots', 'GET', null, silent);
        if (ok) {
            renderSlotGrid('allSlots', data.slots);
        } else {
            showToast('Failed to load slots', 'error');
            document.getElementById('allSlots').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Failed to load slots</h3></div>';
        }
    } catch (e) {
        console.error('Failed to load slots', e);
        document.getElementById('allSlots').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Failed to load slots</h3></div>';
    }
}


// ─── RENDER SLOT GRID ───────────────────────────────────────

function renderSlotGrid(containerId, slots) {
    const container = document.getElementById(containerId);

    if (!slots.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🅿️</div>
                <h3>No Parking Slots</h3>
                <p>No parking slots available at the moment</p>
            </div>
        `;
        return;
    }

    container.innerHTML = slots.map(slot => `
        <div class="slot-card ${slot.Status.toLowerCase()}" 
             onclick="${slot.Status === 'Available' ? `openBookingModal(${slot.SlotID}, '${slot.SlotNumber}')` : ''}"
             title="${slot.Status === 'Available' ? 'Click to book this slot' : 'This slot is booked'}">
            <div class="slot-icon">${slot.Status === 'Available' ? '🚗' : '🔒'}</div>
            <div class="slot-number">${slot.SlotNumber}</div>
            <span class="slot-status">${slot.Status}</span>
        </div>
    `).join('');
}


// ─── BOOKING MODAL ──────────────────────────────────────────

function openBookingModal(slotId, slotNumber) {
    currentSlotId = slotId;
    document.getElementById('modalSlotNumber').textContent = slotNumber;
    document.getElementById('bookingModal').classList.add('show');
}

function closeModal() {
    document.getElementById('bookingModal').classList.remove('show');
    currentSlotId = null;
}

async function confirmBooking() {
    if (!currentSlotId) return;

    const btn = document.getElementById('confirmBookBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Booking...';

    try {
        const { ok, data } = await apiRequest('/api/book', 'POST', { slot_id: currentSlotId });

        if (ok) {
            showToast(`Slot booked successfully! Confirmation email sent.`, 'success');
            closeModal();
            loadOverview();
            loadAllSlots();
            loadMyBookings();
        } else {
            showToast(data.message || 'Booking failed', 'error');
        }
    } catch (e) {
        showToast('Network error. Please try again.', 'error');
    }

    btn.disabled = false;
    btn.textContent = 'Confirm Booking';
}


// ─── LOAD MY BOOKINGS ──────────────────────────────────────

async function loadMyBookings(silent = false) {
    try {
        const { ok, data } = await apiRequest('/api/user/bookings', 'GET', null, silent);
        if (ok) {
            renderBookingsTable(data.bookings);
        } else {
            showToast('Failed to load bookings', 'error');
            document.getElementById('bookingsTable').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Failed to load bookings</h3></div>';
        }
    } catch (e) {
        console.error('Failed to load bookings', e);
        document.getElementById('bookingsTable').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Failed to load bookings</h3></div>';
    }
}

function renderBookingsTable(bookings) {
    const container = document.getElementById('bookingsTable');

    if (!bookings.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📋</div>
                <h3>No Bookings Yet</h3>
                <p>Book a parking slot to see your bookings here</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Booking ID</th>
                    <th>Slot</th>
                    <th>Date</th>
                    <th>Time</th>
                    <th>QR Code</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${bookings.map(b => `
                    <tr>
                        <td>#${b.BookingID}</td>
                        <td><span class="status-badge status-booked">${b.SlotNumber}</span></td>
                        <td>${b.Date}</td>
                        <td>${b.Time}</td>
                        <td>
                            <button class="btn btn-outline btn-sm" onclick="viewQrCode(${b.BookingID})" title="View QR Code">
                                📱 QR
                            </button>
                        </td>
                        <td>
                            <button class="btn btn-danger btn-sm" onclick="openCancelModal(${b.BookingID})">
                                Cancel
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}


// ─── CANCEL BOOKING ─────────────────────────────────────────

function openCancelModal(bookingId) {
    currentBookingId = bookingId;
    document.getElementById('cancelModal').classList.add('show');
}

function closeCancelModal() {
    document.getElementById('cancelModal').classList.remove('show');
    currentBookingId = null;
}

async function confirmCancel() {
    if (!currentBookingId) return;

    const btn = document.getElementById('confirmCancelBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Cancelling...';

    try {
        const { ok, data } = await apiRequest('/api/user/cancel', 'POST', { booking_id: currentBookingId });

        if (ok) {
            showToast('Booking cancelled successfully', 'info');
            closeCancelModal();
            loadOverview();
            loadAllSlots();
            loadMyBookings();
        } else {
            showToast(data.message || 'Cancellation failed', 'error');
        }
    } catch (e) {
        showToast('Network error. Please try again.', 'error');
    }

    btn.disabled = false;
    btn.textContent = 'Cancel Booking';
}


// ─── QR CODE VIEWER ─────────────────────────────────────────

async function viewQrCode(bookingId) {
    try {
        const { ok, data } = await apiRequest(`/api/user/booking/qr/${bookingId}`);

        if (ok) {
            document.getElementById('qrCodeImage').src = data.qr_image;
            const b = data.booking;
            document.getElementById('qrBookingDetails').innerHTML = `
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px;">
                    <div><span style="color: var(--text-muted);">Booking ID:</span> <strong>#${b.BookingID}</strong></div>
                    <div><span style="color: var(--text-muted);">Slot:</span> <strong>${b.SlotNumber}</strong></div>
                    <div><span style="color: var(--text-muted);">Date:</span> <strong>${b.Date}</strong></div>
                    <div><span style="color: var(--text-muted);">Time:</span> <strong>${b.Time}</strong></div>
                </div>
            `;
            document.getElementById('qrModal').classList.add('show');
        } else {
            showToast(data.message || 'Failed to load QR code', 'error');
        }
    } catch (e) {
        showToast('Network error', 'error');
    }
}

function closeQrModal() {
    document.getElementById('qrModal').classList.remove('show');
}

function downloadQrCode() {
    const qrImage = document.getElementById('qrCodeImage').src;
    const bookingDetails = document.getElementById('qrBookingDetails');
    const bookingIdStr = bookingDetails.querySelector('strong')?.textContent.replace('#', '') || 'unknown';

    const link = document.createElement('a');
    link.href = qrImage;
    link.download = `Booking_QR_${bookingIdStr}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('QR Code saved successfully', 'success');
}


// ─── LOGOUT ─────────────────────────────────────────────────

async function handleLogout() {
    try {
        await apiRequest('/api/logout', 'POST');
        window.location.href = '/login';
    } catch (e) {
        window.location.href = '/login';
    }
}

async function deleteAccount() {
    if (!confirm('Are you sure you want to delete your account? This action is permanent and will cancel all your bookings.')) return;

    const { ok, data } = await apiRequest('/api/user/delete-self', 'POST');
    if (ok) {
        alert('Account deleted successfully. You will be logged out.');
        window.location.href = '/login';
    } else {
        showToast(data.message || 'Failed to delete account', 'error');
    }
}


// ─── REAL-TIME UPDATES ──────────────────────────────────────

function startAutoRefresh() {
    refreshInterval = setInterval(() => {
        const activeTab = document.querySelector('.tab-content.active');
        if (activeTab) {
            const id = activeTab.id;
            if (id === 'tab-overview') loadOverview(true);
            else if (id === 'tab-slots') loadAllSlots(true);
            else if (id === 'tab-bookings') loadMyBookings(true);
        }
    }, 120000); // Refresh every 2 minutes to avoid API rate limits
}


// ─── INITIALIZATION ─────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadUserInfo();
    loadOverview();
    startAutoRefresh();
});

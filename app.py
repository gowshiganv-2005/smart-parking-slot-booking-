"""
Smart Slot Parking Booking System - Main Flask Application
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json
import os
from dotenv import load_dotenv
import config

# Load environment variables from .env file
load_dotenv()

import gsheet_manager as db
import email_service
import qr_generator

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Initialize Google Sheets database on startup
try:
    db.init_gsheet()
    print(f"[INFO] Google Sheets database initialized: {config.GSHEET_ID}")
except Exception as e:
    print(f"[ERROR] Failed to initialize Google Sheets: {e}")


# ─── AUTH DECORATORS ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login_page'))
        return f(*args, **kwargs)
    return decorated


# ─── PAGE ROUTES ─────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('login_page'))


@app.before_request
def track_activity():
    if 'user_id' in session and not request.path.startswith('/static'):
        db.update_user_activity(session['user_id'])


@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('user_dashboard'))
    return render_template('login.html')


@app.route('/register')
def register_page():
    return render_template('register.html')


@app.route('/dashboard')
@login_required
def user_dashboard():
    return render_template('user_dashboard.html')


@app.route('/admin')
def admin_login_page():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')


@app.route('/parking-access')
def parking_access():
    booking_id = request.args.get('booking_id', type=int)
    booking = None
    if booking_id:
        booking = db.get_booking_by_id(booking_id)
    return render_template('access_control.html', booking=booking)


# ─── AUTH API ROUTES ─────────────────────────────────────────────

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'User').strip()

    if not all([name, email, password]):
        return jsonify({'success': False, 'message': 'All fields are required'}), 400

    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    # Validate role
    if role not in ['User', 'Admin']:
        role = 'User'

    hashed = generate_password_hash(password)
    user = db.register_user(name, email, hashed, data.get('phone', ''), role)

    if not user:
        print(f"[AUTH] Registration failed: Email {email} already exists")
        return jsonify({'success': False, 'message': 'Email already registered'}), 409

    db.log_activity(user['UserID'], user['Name'], user['Email'], f'Account Created ({role})')
    print(f"[AUTH] User registered: {email} as {role}")
    return jsonify({'success': True, 'message': 'Registration successful! Please login.'})


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    
    print(f"[DEBUG] Login attempt for: {email}")

    if not all([email, password]):
        return jsonify({'success': False, 'message': 'Email and password are required'}), 400

    # First check: Is this the master admin username/password?
    if email == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
        session['is_admin'] = True
        session['user_name'] = 'Admin'
        session['user_email'] = config.ADMIN_EMAIL
        db.log_activity(0, 'Admin', config.ADMIN_EMAIL, 'Admin Login')
        print(f"[AUTH] Master Admin logged in via unified login")
        return jsonify({'success': True, 'message': 'Admin login successful', 'role': 'admin'})

    # Second check: Email-based user lookup
    user = db.get_user_by_email(email)
    if not user:
        print(f"[AUTH] Login failed: User {email} not found")
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
    
    if not check_password_hash(user['Password'], password):
        print(f"[AUTH] Login failed: Wrong password for {email}")
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

    session['user_id'] = user['UserID']
    session['user_name'] = user['Name']
    session['user_email'] = user['Email']
    
    user_role = user.get('Role', 'User')
    session['user_role'] = user_role
    
    # If user registered as Admin, set admin session too
    if user_role == 'Admin':
        session['is_admin'] = True

    db.log_activity(user['UserID'], user['Name'], user['Email'], 'Login')
    print(f"[AUTH] User logged in: {email} (Role: {user_role})")
    return jsonify({'success': True, 'message': 'Login successful', 'role': user_role.lower()})


@app.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
        session['is_admin'] = True
        db.log_activity(0, 'Admin', config.ADMIN_EMAIL, 'Admin Login')
        print(f"[AUTH] Admin logged in: {username}")
        return jsonify({'success': True, 'message': 'Admin login successful'})
    
    print(f"[AUTH] Admin login failed for: {username}")
    return jsonify({'success': False, 'message': 'Invalid admin credentials'}), 401


@app.route('/api/logout', methods=['POST'])
def api_logout():
    if 'user_id' in session:
        db.log_activity(session['user_id'], session['user_name'], session['user_email'], 'Logout')
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})


# ─── USER API ROUTES ────────────────────────────────────────────

@app.route('/api/user/info')
@login_required
def api_user_info():
    user = db.get_user_by_id(session['user_id'])
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    return jsonify({
        'success': True,
        'user': {
            'UserID': user['UserID'],
            'Name': user['Name'],
            'Email': user['Email'],
            'Phone': user.get('Phone', 'N/A')
        }
    })


@app.route('/api/slots')
def api_get_slots():
    slots = db.get_all_slots()
    return jsonify({'success': True, 'slots': slots})


@app.route('/api/book', methods=['POST'])
@login_required
def api_book_slot():
    data = request.get_json()
    slot_id = data.get('slot_id')

    if not slot_id:
        return jsonify({'success': False, 'message': 'Slot ID is required'}), 400

    booking = db.create_booking(session['user_id'], slot_id)

    if not booking:
        return jsonify({'success': False, 'message': 'Slot is no longer available'}), 409

    # Send confirmation email to user
    email_service.send_booking_confirmation(
        session['user_email'],
        session['user_name'],
        booking
    )

    # Send notification to admin
    email_service.send_admin_notification(booking)

    db.log_activity(session['user_id'], session['user_name'], session['user_email'], f"Booked Slot {booking['SlotNumber']}")
    return jsonify({'success': True, 'message': 'Slot booked successfully!', 'booking': booking})


@app.route('/api/user/bookings')
@login_required
def api_user_bookings():
    bookings = db.get_user_bookings(session['user_id'])
    return jsonify({'success': True, 'bookings': bookings})


@app.route('/api/user/cancel', methods=['POST'])
@login_required
def api_cancel_booking():
    data = request.get_json()
    booking_id = data.get('booking_id')

    if not booking_id:
        return jsonify({'success': False, 'message': 'Booking ID is required'}), 400

    # Get booking details before cancelling for email
    all_bookings = db.get_user_bookings(session['user_id'])
    booking_info = None
    for b in all_bookings:
        if b['BookingID'] == booking_id:
            booking_info = b
            break

    if not booking_info:
        return jsonify({'success': False, 'message': 'Booking not found'}), 404

    result = db.cancel_booking(booking_id)

    if result:
        email_service.send_cancellation_email(
            session['user_email'],
            session['user_name'],
            booking_info['SlotNumber']
        )
        return jsonify({'success': True, 'message': 'Booking cancelled successfully'})

    return jsonify({'success': False, 'message': 'Failed to cancel booking'}), 400


# ─── ADMIN API ROUTES ───────────────────────────────────────────

@app.route('/api/admin/stats')
@admin_required
def api_admin_stats():
    stats = db.get_dashboard_stats()
    return jsonify({'success': True, 'stats': stats})


@app.route('/api/admin/slots')
@admin_required
def api_admin_slots():
    slots = db.get_all_slots()
    return jsonify({'success': True, 'slots': slots})


@app.route('/api/admin/bookings')
@admin_required
def api_admin_bookings():
    bookings = db.get_all_bookings()
    return jsonify({'success': True, 'bookings': bookings})


@app.route('/api/admin/users')
@admin_required
def api_admin_users():
    users = db.get_all_users()
    return jsonify({'success': True, 'users': users})


@app.route('/api/admin/logs')
@admin_required
def api_admin_logs():
    logs = db.get_all_logs()
    return jsonify({'success': True, 'logs': logs})


@app.route('/api/admin/slots/add', methods=['POST'])
@admin_required
def api_admin_add_slot():
    data = request.get_json()
    slot_number = data.get('slot_number', '').strip()

    if not slot_number:
        return jsonify({'success': False, 'message': 'Slot number is required'}), 400

    slot = db.add_slot(slot_number)
    if not slot:
        return jsonify({'success': False, 'message': 'Slot number already exists'}), 409

    return jsonify({'success': True, 'message': 'Slot added successfully', 'slot': slot})


@app.route('/api/admin/slots/update', methods=['POST'])
@admin_required
def api_admin_update_slot():
    data = request.get_json()
    slot_id = data.get('slot_id')
    status = data.get('status')

    if not slot_id or not status:
        return jsonify({'success': False, 'message': 'Slot ID and Status are required'}), 400

    result = db.update_slot_status(slot_id, status)
    if result:
        db.log_activity(0, 'Admin', config.ADMIN_EMAIL, f"Updated Slot #{slot_id} status to {status}")
        return jsonify({'success': True, 'message': f'Slot status updated to {status}'})
    return jsonify({'success': False, 'message': 'Failed to update slot status'}), 400


@app.route('/api/admin/slots/delete', methods=['POST'])
@admin_required
def api_admin_delete_slot():
    data = request.get_json()
    slot_id = data.get('slot_id')

    if not slot_id:
        return jsonify({'success': False, 'message': 'Slot ID is required'}), 400

    result = db.delete_slot(slot_id)
    if result:
        return jsonify({'success': True, 'message': 'Slot deleted successfully'})
    return jsonify({'success': False, 'message': 'Cannot delete a booked slot'}), 400


@app.route('/api/admin/bookings/cancel', methods=['POST'])
@admin_required
def api_admin_cancel_booking():
    data = request.get_json()
    booking_id = data.get('booking_id')

    if not booking_id:
        return jsonify({'success': False, 'message': 'Booking ID is required'}), 400

    # Get booking details for notification
    all_bookings = db.get_all_bookings()
    booking_info = None
    for b in all_bookings:
        if b['BookingID'] == booking_id:
            booking_info = b
            break

    result = db.cancel_booking(booking_id)

    if result and booking_info:
        email_service.send_cancellation_email(
            booking_info['UserEmail'],
            booking_info['UserName'],
            booking_info['SlotNumber']
        )
        return jsonify({'success': True, 'message': 'Booking cancelled successfully'})

    return jsonify({'success': False, 'message': 'Failed to cancel booking'}), 400


# ─── QR CODE API ROUTES ─────────────────────────────────────────

@app.route('/api/user/booking/qr/<int:booking_id>')
@login_required
def api_user_booking_qr(booking_id):
    """Get QR code image for a specific booking."""
    bookings = db.get_user_bookings(session['user_id'])
    booking = None
    for b in bookings:
        if b['BookingID'] == booking_id:
            booking = b
            break

    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found'}), 404

    qr_data_uri = qr_generator.get_qr_data_uri(booking)
    return jsonify({'success': True, 'qr_image': qr_data_uri, 'booking': booking})


@app.route('/api/access/login', methods=['POST'])
def api_access_login():
    data = request.get_json()
    booking_id = data.get('booking_id')
    
    if not booking_id:
        return jsonify({'success': False, 'message': 'Booking ID is required'}), 400
        
    booking = db.get_booking_by_id(booking_id)
    if not booking:
        return jsonify({'success': False, 'message': 'Invalid booking'}), 404
        
    # Security checks
    from datetime import datetime
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    
    # Only allow login on the same day
    if booking['Date'] != today:
         return jsonify({'success': False, 'message': f'Booking is for date {booking["Date"]}. Cannot check-in today.'}), 400
         
    if booking['UserStatus'] == 'Logged In':
        return jsonify({'success': False, 'message': 'User already logged in'}), 400
        
    if booking['UserStatus'] == 'Logged Out':
        return jsonify({'success': False, 'message': 'Booking already completed (Logged Out)'}), 400

    # Update states
    db.update_booking_access_status(booking_id, 'Logged In', f"{today} {time_str}")
    db.update_slot_status(booking['SlotID'], 'Occupied')
    
    db.log_activity(booking['UserID'], booking['UserName'], booking['UserEmail'], f"Checked-in to Slot {booking['SlotNumber']}")
    
    return jsonify({'success': True, 'message': 'User Successfully Entered Parking'})


@app.route('/api/access/logout', methods=['POST'])
def api_access_logout():
    data = request.get_json()
    booking_id = data.get('booking_id')
    
    if not booking_id:
        return jsonify({'success': False, 'message': 'Booking ID is required'}), 400
        
    booking = db.get_booking_by_id(booking_id)
    if not booking:
        return jsonify({'success': False, 'message': 'Invalid booking'}), 404
        
    if booking['UserStatus'] != 'Logged In':
        return jsonify({'success': False, 'message': 'User is not logged in. Cannot log out.'}), 400

    from datetime import datetime
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')

    # Update states
    db.update_booking_access_status(booking_id, 'Logged Out', f"{today} {time_str}")
    db.update_slot_status(booking['SlotID'], 'Available')
    
    db.log_activity(booking['UserID'], booking['UserName'], booking['UserEmail'], f"Checked-out from Slot {booking['SlotNumber']}")
    
    return jsonify({'success': True, 'message': 'User Successfully Exited Parking'})


@app.route('/api/admin/verify-booking', methods=['POST'])
@admin_required
def api_admin_verify_booking():
    """Verify a booking from scanned QR code data."""
    data = request.get_json()
    qr_data = data.get('qr_data', '')

    booking_id = None
    
    # Try parsing as JSON first (backward compatibility)
    try:
        booking_info = json.loads(qr_data)
        booking_id = booking_info.get('booking_id')
    except:
        # If not JSON, check if it's a URL with booking_id
        if 'booking_id=' in qr_data:
            try:
                booking_id = int(qr_data.split('booking_id=')[1].split('&')[0])
            except:
                pass
        # Or maybe it's just the ID itself
        elif qr_data.isdigit():
            booking_id = int(qr_data)

    if not booking_id:
        return jsonify({'success': False, 'message': 'Invalid QR code format or missing booking ID'}), 400

    # Verify booking exists in database
    active_booking = db.get_booking_by_id(booking_id)

    if active_booking:
        return jsonify({
            'success': True,
            'verified': True,
            'message': 'Booking verified successfully!',
            'booking': active_booking
        })
    else:
        return jsonify({
            'success': True,
            'verified': False,
            'message': 'Booking not found or has been cancelled.'
        })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

"""
Smart Slot Parking Booking System - Main Flask Application
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json
import config
import excel_manager
import email_service
import qr_generator

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Initialize Excel database on startup
try:
    excel_manager.init_excel()
    print(f"[INFO] Excel database initialized at {config.EXCEL_FILE}")
except Exception as e:
    print(f"[ERROR] Failed to initialize Excel: {e}")


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


# ─── AUTH API ROUTES ─────────────────────────────────────────────

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not all([name, email, password]):
        return jsonify({'success': False, 'message': 'All fields are required'}), 400

    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    hashed = generate_password_hash(password)
    user = excel_manager.register_user(name, email, hashed)

    if not user:
        return jsonify({'success': False, 'message': 'Email already registered'}), 409

    return jsonify({'success': True, 'message': 'Registration successful! Please login.'})


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not all([email, password]):
        return jsonify({'success': False, 'message': 'Email and password are required'}), 400

    user = excel_manager.get_user_by_email(email)
    if not user or not check_password_hash(user['Password'], password):
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

    session['user_id'] = user['UserID']
    session['user_name'] = user['Name']
    session['user_email'] = user['Email']

    return jsonify({'success': True, 'message': 'Login successful'})


@app.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({'success': True, 'message': 'Admin login successful'})

    return jsonify({'success': False, 'message': 'Invalid admin credentials'}), 401


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})


# ─── USER API ROUTES ────────────────────────────────────────────

@app.route('/api/user/info')
@login_required
def api_user_info():
    return jsonify({
        'success': True,
        'user': {
            'UserID': session['user_id'],
            'Name': session['user_name'],
            'Email': session['user_email']
        }
    })


@app.route('/api/slots')
def api_get_slots():
    slots = excel_manager.get_all_slots()
    return jsonify({'success': True, 'slots': slots})


@app.route('/api/book', methods=['POST'])
@login_required
def api_book_slot():
    data = request.get_json()
    slot_id = data.get('slot_id')

    if not slot_id:
        return jsonify({'success': False, 'message': 'Slot ID is required'}), 400

    booking = excel_manager.create_booking(session['user_id'], slot_id)

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

    return jsonify({'success': True, 'message': 'Slot booked successfully!', 'booking': booking})


@app.route('/api/user/bookings')
@login_required
def api_user_bookings():
    bookings = excel_manager.get_user_bookings(session['user_id'])
    return jsonify({'success': True, 'bookings': bookings})


@app.route('/api/user/cancel', methods=['POST'])
@login_required
def api_cancel_booking():
    data = request.get_json()
    booking_id = data.get('booking_id')

    if not booking_id:
        return jsonify({'success': False, 'message': 'Booking ID is required'}), 400

    # Get booking details before cancelling for email
    all_bookings = excel_manager.get_user_bookings(session['user_id'])
    booking_info = None
    for b in all_bookings:
        if b['BookingID'] == booking_id:
            booking_info = b
            break

    if not booking_info:
        return jsonify({'success': False, 'message': 'Booking not found'}), 404

    result = excel_manager.cancel_booking(booking_id)

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
    stats = excel_manager.get_dashboard_stats()
    return jsonify({'success': True, 'stats': stats})


@app.route('/api/admin/slots')
@admin_required
def api_admin_slots():
    slots = excel_manager.get_all_slots()
    return jsonify({'success': True, 'slots': slots})


@app.route('/api/admin/bookings')
@admin_required
def api_admin_bookings():
    bookings = excel_manager.get_all_bookings()
    return jsonify({'success': True, 'bookings': bookings})


@app.route('/api/admin/users')
@admin_required
def api_admin_users():
    users = excel_manager.get_all_users()
    return jsonify({'success': True, 'users': users})


@app.route('/api/admin/slots/add', methods=['POST'])
@admin_required
def api_admin_add_slot():
    data = request.get_json()
    slot_number = data.get('slot_number', '').strip()

    if not slot_number:
        return jsonify({'success': False, 'message': 'Slot number is required'}), 400

    slot = excel_manager.add_slot(slot_number)
    if not slot:
        return jsonify({'success': False, 'message': 'Slot number already exists'}), 409

    return jsonify({'success': True, 'message': 'Slot added successfully', 'slot': slot})


@app.route('/api/admin/slots/delete', methods=['POST'])
@admin_required
def api_admin_delete_slot():
    data = request.get_json()
    slot_id = data.get('slot_id')

    if not slot_id:
        return jsonify({'success': False, 'message': 'Slot ID is required'}), 400

    result = excel_manager.delete_slot(slot_id)
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
    all_bookings = excel_manager.get_all_bookings()
    booking_info = None
    for b in all_bookings:
        if b['BookingID'] == booking_id:
            booking_info = b
            break

    result = excel_manager.cancel_booking(booking_id)

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
    bookings = excel_manager.get_user_bookings(session['user_id'])
    booking = None
    for b in bookings:
        if b['BookingID'] == booking_id:
            booking = b
            break

    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found'}), 404

    qr_data_uri = qr_generator.get_qr_data_uri(booking)
    return jsonify({'success': True, 'qr_image': qr_data_uri, 'booking': booking})


@app.route('/api/admin/verify-booking', methods=['POST'])
@admin_required
def api_admin_verify_booking():
    """Verify a booking from scanned QR code data."""
    data = request.get_json()
    qr_data = data.get('qr_data', '')

    try:
        # Parse the QR code JSON data
        booking_info = json.loads(qr_data)

        # Validate it's from our system
        if booking_info.get('system') != 'SmartParking':
            return jsonify({'success': False, 'message': 'Invalid QR code - not from Smart Parking system'}), 400

        booking_id = booking_info.get('booking_id')

        # Verify booking exists in database
        all_bookings = excel_manager.get_all_bookings()
        active_booking = None
        for b in all_bookings:
            if b['BookingID'] == booking_id:
                active_booking = b
                break

        if active_booking:
            return jsonify({
                'success': True,
                'verified': True,
                'message': 'Booking verified successfully!',
                'booking': active_booking
            })
        else:
            # Booking was found in QR but not in active bookings (might be cancelled)
            return jsonify({
                'success': True,
                'verified': False,
                'message': 'Booking not found or has been cancelled.',
                'qr_info': booking_info
            })

    except json.JSONDecodeError:
        return jsonify({'success': False, 'message': 'Invalid QR code format'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error verifying booking: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)

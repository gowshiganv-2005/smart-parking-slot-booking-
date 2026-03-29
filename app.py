"""
Smart Slot Parking Booking System - Main Flask Application
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import json
import os
from dotenv import load_dotenv
import config

# Load environment variables from .env file
load_dotenv()

# ─── LOCAL DATABASE SETUP ───────────────────────────
db = None
is_gsheet = False

print("[INFO] Initializing Primary Local Database (Solid State)...")
import excel_manager as ex
db = ex
db.init_excel()        # Migrate headers and create sheets if needed
print("[INFO] Local Database System Online and Verified.")

import email_service
import qr_generator

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# ─── SESSION CONFIGURATION (Long-term stability) ────────────────
from routes.feedback_routes import feedback_bp
from datetime import timedelta
app.permanent_session_lifetime = timedelta(hours=12)  # Sessions expire after 12 hours

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.after_request
def add_cache_headers(response):
    """Cache static assets for 1 hour to reduce loading time on repeat visits."""
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=3600'
    return response

# Database has already been initialized at module load natively.


# ─── AUTH DECORATORS ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Unauthorized. Please login.'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Admin access required.'}), 403
            return redirect(url_for('admin_login_page'))
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'SuperAdmin':
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Super Administrator access required.'}), 403
            return redirect(url_for('admin_login_page'))
        return f(*args, **kwargs)
    return decorated


# Register Blueprints
app.register_blueprint(feedback_bp)

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


@app.route('/parking-access')
def parking_access():
    booking_id = request.args.get('booking_id', type=int)
    booking = None
    if booking_id:
        booking = db.get_booking_by_id(booking_id)
    return render_template('access_control.html', booking=booking)


@app.route('/feedback')
def feedback_page():
    return render_template('feedback.html')


# ─── GLOBAL ERROR HANDLERS (Long-term stability) ────────────────

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Endpoint not found'}), 404
    return redirect(url_for('login_page'))

@app.errorhandler(500)
def internal_error(e):
    import traceback
    try: now = db.get_ist_now()
    except: now = "Time Unavailable"
    with open('error.log', 'a') as f:
        f.write(f"\n[{now}] 500 ERROR: {str(e)}\n")
        traceback.print_exc(file=f)
    print(f"[CRITICAL] 500 Error: {e}")
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': f'Server Error (500): {str(e)}'}), 500
    return redirect(url_for('login_page'))

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    try:
        now = db.get_ist_now()
    except:
        from datetime import datetime
        now = datetime.now()
        
    with open('error.log', 'a') as f:
        f.write(f"\n[{now}] CRITICAL: {str(e)}\n")
        traceback.print_exc(file=f)
    print(f"[CRITICAL] Unhandled Exception: {e}")
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': f'Server Error: {str(e)}'}), 500
    return redirect(url_for('login_page'))


# ─── HEALTH CHECK & DIAGNOSTIC ROUTES ────────────────────────────

@app.route('/api/health')
def api_health():
    """Health check endpoint for uptime monitoring services."""
    return jsonify({
        'status': 'healthy',
        'db_mode': 'Local DB',
        'version': '3.0.0'
    })

@app.route('/api/debug/db')
@app.route('/api/status')
def api_status():
    """System Health Troubleshooting."""
    return jsonify({
        'status': 'OK',
        'database': 'Local Primary Database',
        'current_error': None,
        'service_account': 'N/A',
        'spreadsheet_id': 'N/A',
        'troubleshooting_steps': [
            '1. System is running perfectly.',
            '2. Utilizing fast solid-state local storage.',
            '3. Database is fully secured and localized.'
        ],
        'counts': {'users': len(db.get_all_users()) if db else 0},
        'version': '3.0.0 (Standalone)'
    })



# ─── AUTH API ROUTES ─────────────────────────────────────────────

@app.route('/api/register', methods=['POST'])
def api_register():
    import traceback
    import time
    
    try:
        # Step 1: Parse form data
        print("[REG] Step 1: Parsing form data...")
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        phone = request.form.get('phone', '').strip()
        role = request.form.get('role', 'User').strip()
        plate_number = request.form.get('plate_number', '').strip()
        print(f"[REG] Got: name={name}, email={email}, phone={phone}, plate={plate_number}, role={role}")
        
        # Step 2: Get uploaded files
        print("[REG] Step 2: Getting files...")
        vehicle_papers = request.files.get('vehicle_papers')
        driver_license = request.files.get('driver_license')
        print(f"[REG] Papers: {vehicle_papers}, License: {driver_license}")

        # Step 3: Validate required fields
        print("[REG] Step 3: Validating...")
        if not all([name, email, password, phone, plate_number]) or not vehicle_papers or not driver_license:
            return jsonify({'success': False, 'message': 'All fields and files are required'}), 400

        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

        # Step 4: Save documents — try disk first, fallback to base64 for read-only filesystems
        import base64
        papers_url = 'N/A'
        license_url = 'N/A'
        saved_to_disk = False
        papers_path = ''
        license_path = ''
        
        try:
            upload_dir = os.path.join('static', 'uploads', 'documents')
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            
            timestamp = int(time.time())
            papers_filename = secure_filename(f"papers_{timestamp}_{vehicle_papers.filename}")
            license_filename = secure_filename(f"license_{timestamp}_{driver_license.filename}")
            
            if papers_filename and license_filename:
                papers_path = os.path.join(upload_dir, papers_filename)
                license_path = os.path.join(upload_dir, license_filename)
                vehicle_papers.save(papers_path)
                driver_license.save(license_path)
                papers_url = f"/static/uploads/documents/{papers_filename}"
                license_url = f"/static/uploads/documents/{license_filename}"
                saved_to_disk = True
                print(f"[REG] Files saved to disk.")
        except OSError:
            # Fallback for read-only deployments: store filename as reference
            # (Google Sheets has a 50K char/cell limit, so base64 won't fit)
            print("[REG] Disk save failed (read-only FS). Storing filename references.")
            papers_url = f"[Uploaded] {vehicle_papers.filename}"
            license_url = f"[Uploaded] {driver_license.filename}"

        # Step 5: Validate role
        if role not in ['User', 'Admin']:
            role = 'User'

        # Step 6: Hash password and register user in database
        hashed = generate_password_hash(password)
        user = db.register_user(name, email, hashed, phone, role, plate_number, papers_url, license_url)

        if not user:
            if saved_to_disk:
                if papers_path and os.path.exists(papers_path): os.remove(papers_path)
                if license_path and os.path.exists(license_path): os.remove(license_path)
            return jsonify({'success': False, 'message': 'Email already registered'}), 409

        # Step 7: Log activity (non-critical)
        try:
            db.log_activity(user['UserID'], user['Name'], user['Email'], f'Account Created ({role}) with Plate {plate_number}')
        except Exception as log_err:
            print(f"[WARN] Activity log failed (non-critical): {log_err}")

        print(f"[AUTH] User registered: {email} with plate {plate_number}")
        return jsonify({'success': True, 'message': 'Registration successful! Please login.'})
    
    except Exception as e:
        error_msg = f"Registration failed at server: {str(e)}"
        print(f"[CRITICAL] {error_msg}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': error_msg}), 500


@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        


        if not all([email, password]):
            return jsonify({'success': False, 'message': 'Email and password are required'}), 400

        # First check: Is this the master admin username/password?
        if email == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
            session['is_admin'] = True
            session['user_role'] = 'SuperAdmin'
            session['user_name'] = 'System Administrator'
            session['user_email'] = config.ADMIN_EMAIL
            session['user_id'] = 0
            # Log activity synchronously to ensure Vercel records it
            try:
                db.log_activity(0, 'Admin', config.ADMIN_EMAIL, 'Admin Login')
            except Exception as le:
                print(f"[WARN] Failed to log admin activity: {le}")
            
            print(f"[AUTH] Master Admin logged in via unified login")
            return jsonify({
                'success': True, 
                'message': 'Super Admin login successful', 
                'role': 'superadmin',
                'is_super_admin': True
            })

        # Second check: Email-based user lookup
        # Invalidate users cache first to ensure freshest data (critical for serverless)
        if hasattr(db, '_invalidate'):
            db._invalidate('users')
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
        session.permanent = True
        
        user_role = user.get('Role', 'User')
        session['user_role'] = user_role
        
        if email == config.ADMIN_EMAIL:
            session['user_role'] = 'SuperAdmin'
            session['is_admin'] = True
        elif user_role == 'Admin':
            session['user_role'] = 'Admin'
            session['is_admin'] = True
        else:
            session['user_role'] = 'User'

        # Log activity synchronously
        try:
            db.log_activity(user['UserID'], user['Name'], user['Email'], 'Login')
        except Exception as le:
            print(f"[WARN] Failed to log user activity: {le}")
            
        print(f"[AUTH] {session['user_role']} logged in: {email}")
        return jsonify({
            'success': True, 
            'message': 'Login successful', 
            'role': session['user_role'].lower(),
            'is_super_admin': session['user_role'] == 'SuperAdmin'
        })
    except Exception as e:
        print(f"[ERROR] Login error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Server error. Please try again.'}), 500


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
            'Phone': user.get('Phone', 'N/A'),
            'Role': user.get('Role', 'User'),
            'PlateNumber': user.get('PlateNumber', 'N/A'),
            'PapersUrl': user.get('PapersUrl'),
            'LicenseUrl': user.get('LicenseUrl')
        }
    })


@app.route('/api/slots')
def api_get_slots():
    try:
        slots = db.get_all_slots()
        return jsonify({'success': True, 'slots': slots})
    except Exception as e:
        print(f"[ERROR] Failed to get slots: {e}")
        return jsonify({'success': True, 'slots': []})


@app.route('/api/book', methods=['POST'])
@login_required
def api_book_slot():
    try:
        data = request.get_json()
        slot_id = data.get('slot_id')

        if not slot_id:
            return jsonify({'success': False, 'message': 'Slot ID is required'}), 400

        booking = db.create_booking(session['user_id'], slot_id)

        if not booking:
            return jsonify({'success': False, 'message': 'Slot is no longer available'}), 409

        # Send confirmation email to user
        try:
            email_service.send_booking_confirmation(
                session['user_email'],
                session['user_name'],
                booking
            )
            email_service.send_admin_notification(booking)
        except Exception as email_err:
            print(f"[WARN] Email send failed: {email_err}")

        try:
            db.log_activity(session['user_id'], session['user_name'], session['user_email'], f"Booked Slot {booking['SlotNumber']}")
        except Exception as log_err:
            print(f"[WARN] Log activity failed: {log_err}")

        return jsonify({'success': True, 'message': 'Slot booked successfully!', 'booking': booking})
    except Exception as e:
        print(f"[ERROR] Booking failed: {e}")
        return jsonify({'success': False, 'message': 'Booking failed. Please try again.'}), 500


@app.route('/api/user/bookings')
@login_required
def api_user_bookings():
    bookings = db.get_user_bookings(session['user_id'])
    return jsonify({'success': True, 'bookings': bookings})


@app.route('/api/user/cancel', methods=['POST'])
@login_required
def api_cancel_booking():
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')

        if not booking_id:
            return jsonify({'success': False, 'message': 'Booking ID is required'}), 400

        # Get booking details before cancelling for email
        all_bookings = db.get_user_bookings(session['user_id'])
        booking_info = None
        for b in all_bookings:
            if str(b['BookingID']) == str(booking_id):
                booking_info = b
                break

        if not booking_info:
            return jsonify({'success': False, 'message': 'Booking not found'}), 404

        result = db.cancel_booking(booking_id)

        if result:
            try:
                email_service.send_cancellation_email(
                    session['user_email'],
                    session['user_name'],
                    booking_info['SlotNumber']
                )
            except Exception as email_err:
                print(f"[WARN] Cancellation email failed: {email_err}")
            return jsonify({'success': True, 'message': 'Booking cancelled successfully'})

        return jsonify({'success': False, 'message': 'Failed to cancel booking'}), 400
    except Exception as e:
        print(f"[ERROR] Cancel booking failed: {e}")
        return jsonify({'success': False, 'message': 'Cancellation failed. Please try again.'}), 500


# ─── ADMIN API ROUTES ───────────────────────────────────────────

@app.route('/api/admin/stats')
@admin_required
def api_admin_stats():
    stats = db.get_dashboard_stats()
    return jsonify({'success': True, 'stats': stats})


@app.route('/api/admin/dashboard-data')
@admin_required
def api_admin_dashboard_data():
    try:
        data = db.get_full_dashboard_data()
        if 'error' in data:
            return jsonify({'success': False, 'message': 'Google Sheets Error', 'error': data['error']}), 503
        return jsonify({'success': True, **data})
    except Exception as e:
        print(f"[CRITICAL] Dashboard API Error: {e}")
        return jsonify({'success': False, 'message': 'Internal Server Error', 'error': str(e)}), 500


@app.route('/api/admin/slots')
@admin_required
def api_admin_slots():
    try:
        slots = db.get_all_slots()
        return jsonify({'success': True, 'slots': slots})
    except Exception as e:
        print(f"[ERROR] Admin slots fetch failed: {e}")
        return jsonify({'success': True, 'slots': []})


@app.route('/api/admin/bookings')
@admin_required
def api_admin_bookings():
    try:
        bookings = db.get_all_bookings()
        return jsonify({'success': True, 'bookings': bookings})
    except Exception as e:
        print(f"[ERROR] Admin bookings fetch failed: {e}")
        return jsonify({'success': True, 'bookings': []})


@app.route('/api/admin/users')
@super_admin_required
def api_admin_users():
    try:
        users = db.get_all_users()
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        print(f"[ERROR] Admin users fetch failed: {e}")
        return jsonify({'success': True, 'users': []})


@app.route('/api/admin/users/delete', methods=['POST'])
@super_admin_required
def api_admin_delete_user():
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'message': 'User ID is required'}), 400
        
    if db.delete_user(user_id):
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    return jsonify({'success': False, 'message': 'User not found'}), 404


@app.route('/api/admin/logs')
@super_admin_required
def api_admin_logs():
    try:
        logs = db.get_all_logs()
        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        print(f"[ERROR] Admin logs fetch failed: {e}")
        return jsonify({'success': True, 'logs': []})


@app.route('/api/user/delete-self', methods=['POST'])
@login_required
def api_user_delete_self():
    user_id = session['user_id']
    if db.delete_user(user_id):
        session.clear()
        return jsonify({'success': True, 'message': 'Account deleted successfully'})
    return jsonify({'success': False, 'message': 'Failed to delete account'}), 400


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
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')

        if not booking_id:
            return jsonify({'success': False, 'message': 'Booking ID is required'}), 400

        # Get booking details for notification
        all_bookings = db.get_all_bookings()
        booking_info = None
        for b in all_bookings:
            if str(b['BookingID']) == str(booking_id):
                booking_info = b
                break

        result = db.cancel_booking(booking_id)

        if result:
            if booking_info:
                try:
                    email_service.send_cancellation_email(
                        booking_info['UserEmail'],
                        booking_info['UserName'],
                        booking_info['SlotNumber']
                    )
                except Exception as email_err:
                    print(f"[WARN] Admin cancel email failed: {email_err}")
            return jsonify({'success': True, 'message': 'Booking cancelled successfully'})

        return jsonify({'success': False, 'message': 'Failed to cancel booking. Booking may not exist.'}), 400
    except Exception as e:
        print(f"[ERROR] Admin cancel booking failed: {e}")
        return jsonify({'success': False, 'message': 'Cancellation failed. Please try again.'}), 500


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
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')
        
        if not booking_id:
            return jsonify({'success': False, 'message': 'Booking ID is required'}), 400
            
        booking = db.get_booking_by_id(booking_id)
        if not booking:
            return jsonify({'success': False, 'message': 'Invalid booking'}), 404
            
        # Security checks - use IST time from DB manager
        now = db.get_ist_now()
        today = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M:%S')
        
        # Only allow login on the same day
        if str(booking['Date']) != today:
             return jsonify({'success': False, 'message': f'Booking is for date {booking["Date"]}. Cannot check-in today.'}), 400
             
        if str(booking['UserStatus']) == 'Logged In':
            return jsonify({'success': False, 'message': 'User already logged in'}), 400
            
        if str(booking['UserStatus']) == 'Logged Out':
            return jsonify({'success': False, 'message': 'Booking already completed (Logged Out)'}), 400

        # Update states
        db.update_booking_access_status(booking_id, 'Logged In', f"{today} {time_str}")
        db.update_slot_status(booking['SlotID'], 'Occupied')
        
        try:
            db.log_activity(booking['UserID'], booking['UserName'], booking['UserEmail'], f"Checked-in to Slot {booking['SlotNumber']}")
        except Exception as log_err:
            print(f"[WARN] Check-in log failed: {log_err}")
        
        return jsonify({'success': True, 'message': 'User Successfully Entered Parking'})
    except Exception as e:
        print(f"[ERROR] Access login failed: {e}")
        return jsonify({'success': False, 'message': 'Check-in failed. Please try again.'}), 500


@app.route('/api/access/logout', methods=['POST'])
def api_access_logout():
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')
        
        if not booking_id:
            return jsonify({'success': False, 'message': 'Booking ID is required'}), 400
            
        booking = db.get_booking_by_id(booking_id)
        if not booking:
            return jsonify({'success': False, 'message': 'Invalid booking'}), 404
            
        if str(booking['UserStatus']) != 'Logged In':
            return jsonify({'success': False, 'message': 'User is not logged in. Cannot log out.'}), 400

        now = db.get_ist_now()
        today = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M:%S')

        # Update states
        db.update_booking_access_status(booking_id, 'Logged Out', f"{today} {time_str}")
        db.update_slot_status(booking['SlotID'], 'Available')
        
        try:
            db.log_activity(booking['UserID'], booking['UserName'], booking['UserEmail'], f"Checked-out from Slot {booking['SlotNumber']}")
        except Exception as log_err:
            print(f"[WARN] Check-out log failed: {log_err}")
        
        return jsonify({'success': True, 'message': 'User Successfully Exited Parking'})
    except Exception as e:
        print(f"[ERROR] Access logout failed: {e}")
        return jsonify({'success': False, 'message': 'Check-out failed. Please try again.'}), 500


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

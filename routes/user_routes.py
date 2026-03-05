from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, current_app
from models.parking_model import ParkingSlot
from models.booking_model import Booking
from models.user_model import User
from bson import ObjectId
from datetime import datetime
from functools import wraps
import email_service

user_bp = Blueprint('user', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@user_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user_name=session.get('user_name'))

@user_bp.route('/api/user/info')
@login_required
def user_info():
    user = User.get_by_id(session['user_id'])
    return jsonify({
        "success": True,
        "user": {
            "UserID": str(user['_id']),
            "Name": user['name'],
            "Email": user['email']
        }
    })

@user_bp.route('/api/slots')
def get_slots():
    slots = ParkingSlot.get_all_slots()
    formatted_slots = []
    for slot in slots:
        formatted_slots.append({
            "SlotID": str(slot['_id']),
            "SlotNumber": slot['slot_number'],
            "Status": slot['status'].capitalize()
        })
    return jsonify({"success": True, "slots": formatted_slots})

@user_bp.route('/api/book', methods=['POST'])
@login_required
def book_slot():
    data = request.get_json()
    slot_id = data.get('slot_id')
    booking_date = datetime.utcnow().strftime('%Y-%m-%d')
    start_time = datetime.utcnow().strftime('%H:%M')
    end_time = "N/A"

    slot = ParkingSlot.get_slot_by_id(slot_id)
    if not slot or slot['status'] != 'available':
        return jsonify({"success": False, "message": "Slot not available"}), 400

    # Create booking record
    booking_res = Booking.create_booking(session['user_id'], slot_id, booking_date, start_time, end_time)
    
    # Update slot status
    ParkingSlot.update_status(slot_id, 'booked', session['user_id'])
    
    # Send Email
    from app import mail # Import here to avoid circular
    email_service.send_booking_confirmation(
        current_app._get_current_object(),
        mail,
        session['user_email'] if 'user_email' in session else User.get_by_id(session['user_id'])['email'],
        session['user_name'],
        slot['slot_number'],
        str(booking_res.inserted_id),
        booking_date,
        start_time
    )
    
    return jsonify({"success": True, "message": "Slot booked successfully"})

@user_bp.route('/api/user/bookings')
@login_required
def my_bookings():
    bookings = Booking.get_user_bookings(session['user_id'])
    formatted_bookings = []
    for b in bookings:
        slot = ParkingSlot.get_slot_by_id(b['slot_id'])
        formatted_bookings.append({
            "BookingID": str(b['_id']),
            "SlotNumber": slot['slot_number'] if slot else "N/A",
            "Date": b['booking_date'],
            "Time": b['start_time'],
            "Status": b['status'].capitalize()
        })
    return jsonify({"success": True, "bookings": formatted_bookings})

@user_bp.route('/api/user/cancel', methods=['POST'])
@login_required
def cancel_booking():
    data = request.get_json()
    booking_id = data.get('booking_id')
    
    booking = Booking.get_booking_by_id(booking_id)
    if not booking or str(booking['user_id']) != session['user_id']:
        return jsonify({"success": False, "message": "Booking not found"}), 404

    # Cancel booking
    Booking.cancel_booking(booking_id)
    
    # Release slot
    ParkingSlot.update_status(booking['slot_id'], 'available')
    
    # Send Email
    from app import mail
    slot = ParkingSlot.get_slot_by_id(booking['slot_id'])
    email_service.send_cancellation_email(
        current_app._get_current_object(),
        mail,
        session.get('user_email', User.get_by_id(session['user_id'])['email']),
        session['user_name'],
        slot['slot_number'] if slot else "N/A"
    )
    
    return jsonify({"success": True, "message": "Booking cancelled"})

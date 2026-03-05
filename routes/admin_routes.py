from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from models.parking_model import ParkingSlot
from models.booking_model import Booking
from models.user_model import User
from bson import ObjectId
from functools import wraps

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/admin/dashboard')
@admin_required
def dashboard():
    return render_template('admin_dashboard.html')

@admin_bp.route('/api/admin/stats')
@admin_required
def get_stats():
    slots = ParkingSlot.get_all_slots()
    total_slots = len(slots)
    booked_slots = len([s for s in slots if s['status'] == 'booked'])
    available_slots = total_slots - booked_slots
    total_users = len(User.get_all_users())
    
    return jsonify({
        "success": True,
        "stats": {
            "total_slots": total_slots,
            "booked_slots": booked_slots,
            "available_slots": available_slots,
            "total_users": total_users
        }
    })

@admin_bp.route('/api/admin/slots')
@admin_required
def get_admin_slots():
    slots = ParkingSlot.get_all_slots()
    formatted_slots = []
    for slot in slots:
        formatted_slots.append({
            "SlotID": str(slot['_id']),
            "SlotNumber": slot['slot_number'],
            "Status": slot['status'].capitalize()
        })
    return jsonify({"success": True, "slots": formatted_slots})

@admin_bp.route('/api/admin/slots/add', methods=['POST'])
@admin_required
def add_slot():
    data = request.get_json()
    slot_number = data.get('slot_number')
    if not slot_number:
        return jsonify({"success": False, "message": "Slot number required"}), 400
    
    result = ParkingSlot.add_slot(slot_number)
    if not result:
        return jsonify({"success": False, "message": "Slot already exists"}), 400
    
    return jsonify({"success": True, "message": "Slot added"})

@admin_bp.route('/api/admin/slots/delete', methods=['POST'])
@admin_required
def delete_slot():
    data = request.get_json()
    slot_id = data.get('slot_id')
    
    success = ParkingSlot.delete_slot(slot_id)
    if success:
        return jsonify({"success": True, "message": "Slot deleted"})
    return jsonify({"success": False, "message": "Slot is booked or not found"}), 400

@admin_bp.route('/api/admin/bookings')
@admin_required
def all_bookings():
    bookings = Booking.get_all_bookings()
    formatted_bookings = []
    for b in bookings:
        user = User.get_by_id(b['user_id'])
        slot = ParkingSlot.get_slot_by_id(b['slot_id'])
        formatted_bookings.append({
            "BookingID": str(b['_id']),
            "UserName": user['name'] if user else "Unknown",
            "UserEmail": user['email'] if user else "N/A",
            "SlotNumber": slot['slot_number'] if slot else "N/A",
            "Date": b['booking_date'],
            "Time": b['start_time'],
            "Status": b['status'].capitalize()
        })
        
    return jsonify({"success": True, "bookings": formatted_bookings})

@admin_bp.route('/api/admin/users')
@admin_required
def all_users():
    users = User.get_all_users()
    formatted_users = []
    for u in users:
        formatted_users.append({
            "UserID": str(u['_id']),
            "Name": u['name'],
            "Email": u['email'],
            "Role": u['role'].capitalize()
        })
    return jsonify({"success": True, "users": formatted_users})

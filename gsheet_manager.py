"""
Google Sheets Database Manager for Smart Parking System
Handles all CRUD operations using Google Sheets as the primary database.
"""

import gspread
from google.oauth2.service_account import Credentials
import config
from datetime import datetime
import threading
import time

# Use a lock to prevent concurrent write issues (though gspread handles some of this)
sheet_lock = threading.Lock()

# SCOPES for Google Sheets and Drive
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

_gc = None
_sh = None

def _get_client():
    """Get the gspread client, initializing if necessary."""
    global _gc, _sh
    if _gc is None:
        credentials = Credentials.from_service_account_file(
            config.GSHEET_CREDENTIALS_FILE,
            scopes=SCOPES
        )
        _gc = gspread.authorize(credentials)
        _sh = _gc.open_by_key(config.GSHEET_ID)
    return _sh

def init_gsheet():
    """Initialize the Google Sheet with required tabs and headers if they don't exist."""
    sh = _get_client()
    
    required_sheets = {
        'Users': ['UserID', 'Name', 'Email', 'Password', 'Phone', 'LastActive'],
        'ParkingSlots': ['SlotID', 'SlotNumber', 'Status'],
        'Bookings': ['BookingID', 'UserID', 'SlotID', 'SlotNumber', 'Date', 'Time', 'UserName', 'UserEmail', 'UserStatus', 'LoginTime', 'LogoutTime'],
        'ActivityLogs': ['LogID', 'UserID', 'UserName', 'UserEmail', 'Action', 'Date', 'Time']
    }
    
    existing_sheets = [ws.title for ws in sh.worksheets()]
    
    for title, headers in required_sheets.items():
        if title not in existing_sheets:
            ws = sh.add_worksheet(title=title, rows="100", cols=str(len(headers)))
            ws.append_row(headers)
            print(f"[INFO] Created sheet: {title}")
        else:
            # Optionally check headers
            pass

    # Initialize default slots if none exist
    ws_slots = sh.worksheet('ParkingSlots')
    if len(ws_slots.get_all_values()) <= 1:
        slots_data = []
        for i in range(1, config.TOTAL_SLOTS + 1):
            slot_id = int(time.time() * 1000) + i
            slots_data.append([slot_id, f"P-{i:02d}", "Available"])
        ws_slots.append_rows(slots_data)
        print(f"[INFO] Initialized {config.TOTAL_SLOTS} default slots.")

# ─── USER OPERATIONS ───────────────────────────────────────────

def get_user_by_email(email):
    """Get user details by email."""
    sh = _get_client()
    ws = sh.worksheet('Users')
    records = ws.get_all_records()
    for row in records:
        if row['Email'].lower() == email.lower():
            return row
    return None

def get_user_by_id(user_id):
    """Get user details by ID."""
    sh = _get_client()
    ws = sh.worksheet('Users')
    records = ws.get_all_records()
    for row in records:
        if str(row['UserID']) == str(user_id):
            return row
    return None

def register_user(name, email, password_hash, phone):
    """Register a new user."""
    if get_user_by_email(email):
        return None
        
    sh = _get_client()
    ws = sh.worksheet('Users')
    user_id = int(time.time() * 1000)
    new_user = [user_id, name, email, password_hash, phone, 'N/A']
    
    with sheet_lock:
        ws.append_row(new_user)
        
    return {
        'UserID': user_id,
        'Name': name,
        'Email': email,
        'Phone': phone,
        'LastActive': 'N/A'
    }

def get_all_users():
    """Get all registered users."""
    sh = _get_client()
    ws = sh.worksheet('Users')
    return ws.get_all_records()

def update_user_activity(user_id):
    """Update user's last active timestamp."""
    sh = _get_client()
    ws = sh.worksheet('Users')
    records = ws.get_all_records()
    
    for i, row in enumerate(records):
        if str(row['UserID']) == str(user_id):
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with sheet_lock:
                # Row index is i + 2 because of header and 1-based indexing
                ws.update_cell(i + 2, 6, now)
            return True
    return False

# ─── SLOT OPERATIONS ───────────────────────────────────────────

def get_all_slots():
    """Get all parking slots."""
    sh = _get_client()
    ws = sh.worksheet('ParkingSlots')
    return ws.get_all_records()

def add_slot(slot_number):
    """Add a new parking slot."""
    sh = _get_client()
    ws = sh.worksheet('ParkingSlots')
    slot_id = int(time.time() * 1000)
    
    with sheet_lock:
        ws.append_row([slot_id, slot_number, "Available"])
    return True

def delete_slot(slot_id):
    """Delete a parking slot."""
    sh = _get_client()
    ws = sh.worksheet('ParkingSlots')
    records = ws.get_all_records()
    
    for i, row in enumerate(records):
        if str(row['SlotID']) == str(slot_id):
            with sheet_lock:
                ws.delete_rows(i + 2)
            return True
    return False

def update_slot_status(slot_id, status):
    """Update slot availability status."""
    sh = _get_client()
    ws = sh.worksheet('ParkingSlots')
    records = ws.get_all_records()
    
    for i, row in enumerate(records):
        if str(row['SlotID']) == str(slot_id):
            with sheet_lock:
                ws.update_cell(i + 2, 3, status)
            return True
    return False

# ─── BOOKING OPERATIONS ────────────────────────────────────────

def create_booking(user_id, slot_id):
    """Book a parking slot."""
    sh = _get_client()
    user = get_user_by_id(user_id)
    ws_slots = sh.worksheet('ParkingSlots')
    slots = ws_slots.get_all_records()
    
    target_slot = None
    slot_row_idx = -1
    for i, s in enumerate(slots):
        if str(s['SlotID']) == str(slot_id) and s['Status'] == 'Available':
            target_slot = s
            slot_row_idx = i + 2
            break
            
    if not target_slot:
        return None
        
    ws_bookings = sh.worksheet('Bookings')
    booking_id = int(time.time() * 1000)
    now = datetime.now()
    
    with sheet_lock:
        # Mark slot as booked
        ws_slots.update_cell(slot_row_idx, 3, 'Booked')
        
        # Create booking entry
        booking_data = [
            booking_id, user_id, slot_id, target_slot['SlotNumber'],
            now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'),
            user['Name'], user['Email'], 'Pending', 'N/A', 'N/A'
        ]
        ws_bookings.append_row(booking_data)
        
    return {
        'BookingID': booking_id,
        'UserID': user_id,
        'SlotID': slot_id,
        'SlotNumber': target_slot['SlotNumber'],
        'Date': now.strftime('%Y-%m-%d'),
        'Time': now.strftime('%H:%M:%S'),
        'UserName': user['Name'],
        'UserEmail': user['Email'],
        'UserStatus': 'Pending',
        'LoginTime': 'N/A',
        'LogoutTime': 'N/A'
    }

def get_booking_by_id(booking_id):
    """Get booking by ID."""
    sh = _get_client()
    ws = sh.worksheet('Bookings')
    records = ws.get_all_records()
    for row in records:
        if str(row['BookingID']) == str(booking_id):
            return row
    return None

def update_booking_access_status(booking_id, status, time_str=None):
    """Update booking status (Login/Logout)."""
    sh = _get_client()
    ws = sh.worksheet('Bookings')
    records = ws.get_all_records()
    
    for i, row in enumerate(records):
        if str(row['BookingID']) == str(booking_id):
            with sheet_lock:
                ws.update_cell(i + 2, 9, status) # UserStatus
                if status == 'Logged In' and time_str:
                    ws.update_cell(i + 2, 10, time_str) # LoginTime
                elif status == 'Logged Out' and time_str:
                    ws.update_cell(i + 2, 11, time_str) # LogoutTime
            return True
    return False

def cancel_booking(booking_id):
    """Cancel a booking."""
    sh = _get_client()
    ws_bookings = sh.worksheet('Bookings')
    records = ws_bookings.get_all_records()
    
    for i, row in enumerate(records):
        if str(row['BookingID']) == str(booking_id):
            slot_id = row['SlotID']
            with sheet_lock:
                # Free the slot
                update_slot_status(slot_id, 'Available')
                # Delete booking
                ws_bookings.delete_rows(i + 2)
            return True
    return False

def get_all_bookings():
    """Get all bookings."""
    sh = _get_client()
    ws = sh.worksheet('Bookings')
    return ws.get_all_records()

def get_user_bookings(user_id):
    """Get bookings for a specific user."""
    sh = _get_client()
    ws = sh.worksheet('Bookings')
    records = ws.get_all_records()
    return [r for r in records if str(r['UserID']) == str(user_id)]

# ─── STATS & LOGS ──────────────────────────────────────────────

def get_dashboard_stats():
    """Get stats for admin panel."""
    users = get_all_users()
    slots = get_all_slots()
    bookings = get_all_bookings()
    
    available = len([s for s in slots if s['Status'] == 'Available'])
    parked = len([b for b in bookings if b['UserStatus'] == 'Logged In'])
    
    return {
        'total_users': len(users),
        'total_slots': len(slots),
        'available_slots': available,
        'booked_slots': len(slots) - available,
        'total_bookings': len(bookings),
        'parked_vehicles': parked
    }

def log_activity(user_id, name, email, action):
    """Log an activity."""
    sh = _get_client()
    ws = sh.worksheet('ActivityLogs')
    log_id = int(time.time() * 1000)
    now = datetime.now()
    
    log_data = [
        log_id, user_id, name, email, action,
        now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S')
    ]
    with sheet_lock:
        ws.append_row(log_data)
    return True

def get_all_logs():
    """Get all activity logs."""
    sh = _get_client()
    ws = sh.worksheet('ActivityLogs')
    return ws.get_all_records()

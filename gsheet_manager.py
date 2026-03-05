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

# Cache for frequently accessed data to avoid 429 Quota Errors
_cache = {}
_cache_expiry = 60 # seconds

_gc = None
_sh = None

def _get_cached_data(key, fetch_func):
    """Get data from cache if not expired, otherwise fetch new data."""
    now = time.time()
    if key in _cache and (now - _cache[key]['time']) < _cache_expiry:
        return _cache[key]['data']
    
    data = fetch_func()
    # If the fetch fails with APIError, it will bubbled up but won't cache
    _cache[key] = {'time': now, 'data': data}
    return data

def _get_client():
    """Get the gspread client, initializing if necessary."""
    global _gc, _sh
    if _gc is None:
        # Check if credential JSON is provided in Environment Variables first
        if config.GSHEET_CREDENTIALS_JSON:
            import json
            info = json.loads(config.GSHEET_CREDENTIALS_JSON)
            credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            # Fallback to local file
            credentials = Credentials.from_service_account_file(
                config.GSHEET_CREDENTIALS_FILE,
                scopes=SCOPES
            )
        _gc = gspread.authorize(credentials)
        try:
            _sh = _gc.open_by_key(config.GSHEET_ID)
        except Exception as e:
            print(f"[ERROR] Could not open Google Sheet {config.GSHEET_ID}: {e}")
            raise e
    return _sh

def init_gsheet():
    """Initialize the Google Sheet with required tabs and headers if they don't exist."""
    sh = _get_client()
    
    required_sheets = {
        'Users': ['UserID', 'Name', 'Email', 'Password', 'Phone', 'Role', 'LastActive'],
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
    def fetch():
        sh = _get_client()
        return sh.worksheet('Users').get_all_records()
    
    records = _get_cached_data('users', fetch)
    for row in records:
        if str(row['Email']).lower() == str(email).lower():
            return row
    return None

def get_user_by_id(user_id):
    """Get user details by ID."""
    def fetch():
        sh = _get_client()
        return sh.worksheet('Users').get_all_records()
    
    records = _get_cached_data('users', fetch)
    for row in records:
        if str(row['UserID']) == str(user_id):
            return row
    return None

def register_user(name, email, password_hash, phone, role='User'):
    """Register a new user."""
    if get_user_by_email(email):
        return None
        
    sh = _get_client()
    ws = sh.worksheet('Users')
    user_id = int(time.time() * 1000)
    new_user = [user_id, name, email, password_hash, phone, role, 'N/A']
    
    with sheet_lock:
        ws.append_row(new_user)
        # Clear cache after write
        if 'users' in _cache: del _cache['users']
        
    return {
        'UserID': user_id,
        'Name': name,
        'Email': email,
        'Phone': phone,
        'Role': role,
        'LastActive': 'N/A'
    }

def get_all_users():
    """Get all registered users."""
    def fetch():
        sh = _get_client()
        return sh.worksheet('Users').get_all_records()
    return _get_cached_data('users', fetch)

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
                ws.update_cell(i + 2, 7, now)
            return True
    return False

# ─── SLOT OPERATIONS ───────────────────────────────────────────

def get_all_slots():
    """Get all parking slots."""
    def fetch():
        sh = _get_client()
        return sh.worksheet('ParkingSlots').get_all_records()
    return _get_cached_data('slots', fetch)

def add_slot(slot_number):
    """Add a new parking slot."""
    sh = _get_client()
    ws = sh.worksheet('ParkingSlots')
    slot_id = int(time.time() * 1000)
    
    with sheet_lock:
        ws.append_row([slot_id, slot_number, "Available"])
        if 'slots' in _cache: del _cache['slots']
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
                if 'slots' in _cache: del _cache['slots']
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
                if 'slots' in _cache: del _cache['slots']
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
                if 'bookings' in _cache: del _cache['bookings']
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
                if 'bookings' in _cache: del _cache['bookings']
            return True
    return False

def get_all_bookings():
    """Get all bookings."""
    def fetch():
        sh = _get_client()
        return sh.worksheet('Bookings').get_all_records()
    return _get_cached_data('bookings', fetch)

def get_user_bookings(user_id):
    """Get bookings for a specific user."""
    records = get_all_bookings()
    return [r for r in records if str(r['UserID']) == str(user_id)]

# ─── STATS & LOGS ──────────────────────────────────────────────

def get_dashboard_stats():
    """Get stats for admin panel."""
    def fetch():
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
    return _get_cached_data('dashboard_stats', fetch)

def get_full_dashboard_data():
    """Get all data needed for admin dashboard in one go using parallel fetching."""
    from concurrent.futures import ThreadPoolExecutor
    
    def fetch_all():
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_users = executor.submit(get_all_users)
            future_slots = executor.submit(get_all_slots)
            future_bookings = executor.submit(get_all_bookings)
            
            users = future_users.result()
            slots = future_slots.result()
            bookings = future_bookings.result()
            
            available = len([s for s in slots if s['Status'] == 'Available'])
            parked = len([b for b in bookings if b['UserStatus'] == 'Logged In'])
            
            return {
                'stats': {
                    'total_users': len(users),
                    'total_slots': len(slots),
                    'available_slots': available,
                    'booked_slots': len(slots) - available,
                    'total_bookings': len(bookings),
                    'parked_vehicles': parked
                },
                'slots': slots,
                'bookings': bookings
            }
            
    try:
        return _get_cached_data('full_dashboard', fetch_all)
    except Exception as e:
        print(f"[ERROR] Full dashboard fetch failed: {e}")
        # Return empty data if fetch fails to avoid crashing
        return {
            'stats': {'total_users': 0, 'total_slots': 0, 'available_slots': 0, 'booked_slots': 0, 'total_bookings': 0, 'parked_vehicles': 0},
            'slots': [],
            'bookings': [],
            'error': str(e)
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

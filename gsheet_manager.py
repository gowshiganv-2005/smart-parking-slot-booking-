"""
Google Sheets Database Manager for Smart Parking System
Handles all CRUD operations using Google Sheets as the primary database.
"""

import gspread
from google.oauth2.service_account import Credentials
import config
import os
from datetime import datetime
import threading
import time

# Use a re-entrant lock to prevent deadlocks when functions call each other
sheet_lock = threading.RLock()

# SCOPES for Google Sheets and Drive
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Cache for frequently accessed data to avoid 429 Quota Errors and slow loading
_cache = {}
_CACHE_TTL = {
    'slots':    300,   # 5 min — slots don't change often
    'users':    120,   # 2 min — user list changes occasionally
    'bookings': 60,    # 1 min — bookings change more often
    'logs':     300,   # 5 min — logs are append-only
    'stats':    60,    # 1 min — stats must be reasonably fresh
}
_DEFAULT_CACHE_TTL = 120   # 2 min fallback

_gc = None
_sh = None
_ws_cache = {}   # Worksheet object cache (avoids repeated sh.worksheet() calls)

def _get_cached_data(key, fetch_func):
    """Get data from cache if not expired, otherwise fetch new data."""
    now = time.time()
    ttl = _CACHE_TTL.get(key, _DEFAULT_CACHE_TTL)
    if key in _cache and (now - _cache[key]['time']) < ttl:
        return _cache[key]['data']
    data = fetch_func()
    _cache[key] = {'time': now, 'data': data}
    return data

def _invalidate(*keys):
    """Invalidate specific cache keys."""
    for k in keys:
        _cache.pop(k, None)

def _get_ws(name):
    """Get (and cache) a worksheet object to avoid repeated API calls."""
    if name not in _ws_cache:
        sh = _get_client()
        _ws_cache[name] = sh.worksheet(name)
    return _ws_cache[name]

def _get_client():
    """Get the gspread client, initializing if necessary."""
    global _gc, _sh
    if _sh is not None:
        return _sh
    
    with sheet_lock:
        if _sh is not None:
            return _sh
        # Check if credential JSON is provided in Environment Variables first
        if config.GSHEET_CREDENTIALS_JSON:
            import json
            info = json.loads(config.GSHEET_CREDENTIALS_JSON)
            credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            # Fallback to local file - check multiple possible paths
            possible_paths = [
                config.GSHEET_CREDENTIALS_FILE,
                os.path.join(os.path.dirname(os.path.abspath(__file__)), config.GSHEET_CREDENTIALS_FILE),
                os.path.join(os.getcwd(), config.GSHEET_CREDENTIALS_FILE)
            ]
            
            found_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    found_path = path
                    break
            
            if not found_path:
                msg = f"Credentials file not found in any of: {possible_paths}. Please set GSHEET_CREDENTIALS_JSON environment variable."
                print(f"[ERROR] {msg}")
                raise FileNotFoundError(msg)
                
            credentials = Credentials.from_service_account_file(
                found_path,
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
    records = _get_cached_data('users', lambda: _get_ws('Users').get_all_records())
    for row in records:
        if str(row.get('Email', '')).lower() == str(email).lower():
            return row
    return None

def get_user_by_id(user_id):
    """Get user details by ID."""
    records = _get_cached_data('users', lambda: _get_ws('Users').get_all_records())
    for row in records:
        if str(row.get('UserID', '')) == str(user_id):
            return row
    return None

def register_user(name, email, password_hash, phone, role='User'):
    """Register a new user."""
    if get_user_by_email(email):
        return None
    user_id = int(time.time() * 1000)
    new_user = [user_id, name, email, password_hash, phone, role, 'N/A']
    with sheet_lock:
        _get_ws('Users').append_row(new_user)
        _invalidate('users')
    return {'UserID': user_id, 'Name': name, 'Email': email, 'Phone': phone, 'Role': role, 'LastActive': 'N/A'}

def get_all_users():
    """Get all registered users with data cleaning for shifted rows."""
    def fetch():
        sh = _get_client()
        records = sh.worksheet('Users').get_all_records()
        clean_records = []
        for r in records:
            # Check for data shift bug (UserID is missing or shifted)
            if not r.get('UserID') or r.get('UserID') == '#':
                # Attempt to recover by looking at other fields (Name might contain ID)
                if str(r.get('Name', '')).isnumeric() and len(str(r.get('Name', ''))) > 10:
                    r['UserID'] = r['Name']
                    r['Name'] = r.get('Email', 'Unknown')
                    r['Email'] = r.get('Password', 'Unknown')
                    r['Phone'] = r.get('Role', 'N/A')
                    r['Role'] = r.get('LastActive', 'User')
            
            # Filter out rows that are clearly empty or just placeholders
            if r.get('UserID') and str(r.get('UserID')).strip() != '' and str(r.get('UserID')) != '#':
                clean_records.append(r)
        return clean_records
    return _get_cached_data('users', fetch)

def delete_user(user_id):
    """Delete a user account."""
    ws = _get_ws('Users')
    records = ws.get_all_records()
    for i, row in enumerate(records):
        if str(row.get('UserID', '')) == str(user_id):
            with sheet_lock:
                ws.delete_rows(i + 2)
                _invalidate('users')
            return True
    return False

def update_user_activity(user_id):
    """Update user's last active timestamp — done asynchronously, skip if slow."""
    try:
        ws = _get_ws('Users')
        records = _get_cached_data('users', lambda: ws.get_all_records())
        for i, row in enumerate(records):
            if str(row.get('UserID', '')) == str(user_id):
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ws.update_cell(i + 2, 7, now)
                return True
    except Exception:
        pass  # Non-critical — don't block login if this fails
    return False

# ─── SLOT OPERATIONS ───────────────────────────────────────────

def get_all_slots():
    """Get all parking slots."""
    return _get_cached_data('slots', lambda: _get_ws('ParkingSlots').get_all_records())

def add_slot(slot_number):
    """Add a new parking slot."""
    slot_id = int(time.time() * 1000)
    with sheet_lock:
        _get_ws('ParkingSlots').append_row([slot_id, slot_number, 'Available'])
        _invalidate('slots', 'stats')
    return True

def delete_slot(slot_id):
    """Delete a parking slot."""
    ws = _get_ws('ParkingSlots')
    records = ws.get_all_records()
    for i, row in enumerate(records):
        if str(row.get('SlotID', '')) == str(slot_id):
            with sheet_lock:
                ws.delete_rows(i + 2)
                _invalidate('slots', 'stats')
            return True
    return False

def update_slot_status(slot_id, status):
    """Update slot availability status."""
    ws = _get_ws('ParkingSlots')
    records = ws.get_all_records()
    for i, row in enumerate(records):
        if str(row.get('SlotID', '')) == str(slot_id):
            with sheet_lock:
                ws.update_cell(i + 2, 3, status)
                _invalidate('slots', 'stats')
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
    records = _get_cached_data('bookings', lambda: _get_ws('Bookings').get_all_records())
    for row in records:
        if str(row.get('BookingID', '')) == str(booking_id):
            return row
    return None

def update_booking_access_status(booking_id, status, time_str=None):
    """Update booking status (Check-in/Check-out)."""
    ws = _get_ws('Bookings')
    records = ws.get_all_records()
    for i, row in enumerate(records):
        if str(row.get('BookingID', '')) == str(booking_id):
            with sheet_lock:
                ws.update_cell(i + 2, 9, status)
                if (status == 'Checked In' or status == 'Logged In') and time_str:
                    ws.update_cell(i + 2, 10, time_str)
                elif (status == 'Checked Out' or status == 'Logged Out') and time_str:
                    ws.update_cell(i + 2, 11, time_str)
                _invalidate('bookings', 'stats', 'full_dashboard')
            return True
    return False

def cancel_booking(booking_id):
    """Cancel a booking."""
    ws_bookings = _get_ws('Bookings')
    records = ws_bookings.get_all_records()
    for i, row in enumerate(records):
        if str(row.get('BookingID', '')) == str(booking_id):
            slot_id = row.get('SlotID')
            with sheet_lock:
                update_slot_status(slot_id, 'Available')
                ws_bookings.delete_rows(i + 2)
                _invalidate('bookings', 'slots', 'stats', 'full_dashboard')
            return True
    return False

def get_all_bookings():
    """Get all bookings."""
    return _get_cached_data('bookings', lambda: _get_ws('Bookings').get_all_records())

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

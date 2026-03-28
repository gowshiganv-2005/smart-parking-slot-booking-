"""
Google Sheets Database Manager for Smart Parking System
Handles all CRUD operations using Google Sheets as the primary database.
"""

import gspread
from google.oauth2.service_account import Credentials
import config
import os
from datetime import datetime, timedelta
import threading
import time

def get_ist_now():
    """Get current time in IST (UTC+5:30)."""
    # Force +5:30 offset to handle serverless/UTC servers
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

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
    'slots':           30,    # 30s — must reflect bookings quickly
    'users':           120,   # 2 min — user list changes rarely
    'bookings':        30,    # 30s — bookings change often
    'logs':            300,   # 5 min — logs are append-only
    'stats':           30,    # 30s — derived from slots/bookings
    'dashboard_stats': 30,    # 30s
    'full_dashboard':  30,    # 30s
}
_DEFAULT_CACHE_TTL = 60   # 1 min fallback

_gc = None
_sh = None
_ws_cache = {}   # Worksheet object cache (avoids repeated sh.worksheet() calls)

def _get_cached_data(key, fetch_func):
    """Get data from cache if not expired, otherwise fetch new data with retries.
    
    NOTE: No sheet_lock here! The lock caused a DEADLOCK when get_full_dashboard_data
    held the lock via _get_cached_data, then ThreadPoolExecutor child threads tried 
    to call get_all_users/get_all_slots which also called _get_cached_data and tried 
    to acquire the same lock from a different thread. Individual write operations 
    (append_row, update_cell) already use their own sheet_lock.
    """
    now = time.time()
    ttl = _CACHE_TTL.get(key, _DEFAULT_CACHE_TTL)
    
    # Check if data exists and is fresh
    if key in _cache:
        cached_val, timestamp = _cache[key]
        if now - timestamp < ttl:
            return cached_val
        
        # If slightly expired (within 3x TTL), return stale data but refresh in background
        if now - timestamp < (ttl * 3):
            def refresh():
                try:
                    new_val = fetch_func()
                    _cache[key] = (new_val, time.time())
                except:
                    pass
            threading.Thread(target=refresh, daemon=True).start()
            return cached_val

    # Fresh fetch required — NO lock here (prevents deadlock with ThreadPoolExecutor)
    retries = 2
    last_error = None
    for i in range(retries):
        try:
            data = fetch_func()
            _cache[key] = (data, time.time())
            return data
        except Exception as e:
            last_error = e
            time.sleep(0.5)
            print(f"[WARN] Cache fetch retry {i+1} for {key}: {e}")
    
    # If all retries fail, return stale data as last resort
    if key in _cache:
        return _cache[key][0]
        
    raise last_error

def _invalidate(*keys):
    """Invalidate specific cache keys."""
    for key in keys:
        if key in _cache:
            del _cache[key]

def _get_ws(name):
    """Get (and cache) a worksheet object to avoid repeated API calls."""
    if name not in _ws_cache:
        try:
            sh = _get_client()
            _ws_cache[name] = sh.worksheet(name)
        except Exception as e:
            print(f"[ERROR] Failed to access worksheet {name}: {e}")
            raise e
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
        'Users': ['UserID', 'Name', 'Email', 'Password', 'Phone', 'Role', 'PlateNumber', 'PapersUrl', 'LicenseUrl', 'LastActive'],
        'ParkingSlots': ['SlotID', 'SlotNumber', 'Status'],
        'Bookings': ['BookingID', 'UserID', 'SlotID', 'SlotNumber', 'Date', 'Time', 'UserName', 'UserEmail', 'UserStatus', 'LoginTime', 'LogoutTime'],
        'ActivityLogs': ['LogID', 'UserID', 'UserName', 'UserEmail', 'Action', 'Date', 'Time'],
        'Feedbacks': ['FeedbackID', 'Name', 'Email', 'Rating', 'Feedback', 'Date', 'Time', 'CreatedAt']
    }
    
    existing_sheets = [ws.title for ws in sh.worksheets()]
    
    for title, headers in required_sheets.items():
        if title not in existing_sheets:
            ws = sh.add_worksheet(title=title, rows="100", cols=str(len(headers)))
            ws.append_row(headers)
            print(f"[INFO] Created sheet: {title}")
        else:
            # Force-update headers every time to ensure columns like PlateNumber exist
            # This is safer than just checking first_row != headers
            ws = _get_ws(title)
            try:
                # Use batch update for row 1 to ensure all headers ARE present
                print(f"[INFO] Force-syncing headers for: {title}")
                ws.update('A1', [headers])
            except Exception as ue:
                print(f"[WARN] Partial header update for {title}: {ue}")


    # Ensure default data is present (e.g., if sheet was manually created but empty)
    ws_slots = _get_ws('ParkingSlots')
    # Check if there are any rows below the header
    records = ws_slots.get_all_records()
    if not records:
        print(f"[INFO] Seeding default slots to ParkingSlots...")
        slots_data = []
        for i in range(1, config.TOTAL_SLOTS + 1):
            slot_id = int(time.time() * 1000) + i
            slots_data.append([slot_id, f"P-{i:03d}", "Available"])
        ws_slots.append_rows(slots_data)
        _invalidate('slots', 'stats')


# ─── USER OPERATIONS ───────────────────────────────────────────

def get_user_by_email(email):
    """Get user details by email with data cleaning and cache awareness."""
    try:
        if not email: return None
        # Always use get_all_users() which has the data shift cleaning logic
        records = get_all_users()
        target = str(email).strip().lower()
        for row in records:
            actual = str(row.get('Email', '')).strip().lower()
            if actual == target:
                return row
    except Exception as e:
        print(f"[ERROR] get_user_by_email failed: {e}")
    return None

def get_user_by_id(user_id):
    """Get user details by ID with data cleaning."""
    try:
        # Always use get_all_users() for cleaning and recovery logic
        records = get_all_users()
        for row in records:
            if str(row.get('UserID', '')) == str(user_id):
                return row
    except Exception as e:
        print(f"[ERROR] get_user_by_id failed: {e}")
    return None

def register_user(name, email, password_hash, phone, role='User', plate_number='N/A', papers_url='N/A', license_url='N/A'):
    """Register a new user with vehicle details."""
    if get_user_by_email(email):
        return None
    user_id = int(time.time() * 1000)
    new_user = [user_id, name, email, password_hash, phone, role, plate_number, papers_url, license_url, 'N/A']
    with sheet_lock:
        _get_ws('Users').append_row(new_user)
        _invalidate('users')
    return {
        'UserID': user_id, 
        'Name': name, 
        'Email': email, 
        'Phone': phone, 
        'Role': role, 
        'PlateNumber': plate_number,
        'PapersUrl': papers_url,
        'LicenseUrl': license_url,
        'LastActive': 'N/A'
    }

def _get_flexible_key(row, key_variations, default='N/A'):
    """Search for data using multiple possible key names (handling case/spaces)."""
    if not row: return default
    for k in key_variations:
        if k in row and row[k] and str(row[k]).strip() != '':
            return row[k]
    # Fallback to similar looking keys if exact match not found
    for rk, rv in row.items():
        if any(v.lower().replace(' ', '') == rk.lower().replace(' ', '') for v in key_variations):
            if rv and str(rv).strip() != '':
                return rv
    return default

def _clean_data_row(row, schema_type):
    """Normalize and clean a data row regardless of header shifts or renaming."""
    if not row: return None
    
    # Define primary mappings to handle shifts
    if schema_type == 'users':
        uid = _get_flexible_key(row, ['UserID', 'User ID', 'uid', 'ID'])
        if not uid or str(uid) == '#':
            # Attempt to recover from a shift where ID moved into another column
            if str(row.get('Name', '')).isnumeric() and len(str(row.get('Name', ''))) > 10:
                uid = row.get('Name')
            else:
                return None # Drop truly bad rows
        
        # Build normalized output based on best-guess columns
        clean = {
            'UserID': uid,
            'Name': _get_flexible_key(row, ['Name', 'Full Name']),
            'Email': _get_flexible_key(row, ['Email', 'Email Address']),
            'Password': _get_flexible_key(row, ['Password'], ''),
            'Phone': _get_flexible_key(row, ['Phone', 'PhoneNumber', 'Phone Number', 'PhoneNo']),
            'Role': _get_flexible_key(row, ['Role', 'UserType', 'AccountType'], 'User'),
            'PlateNumber': _get_flexible_key(row, ['PlateNumber', 'NumberPlate', 'VehiclePlate', 'Plate', 'Vehicle Number Plate']),
            'PapersUrl': _get_flexible_key(row, ['PapersUrl', 'VehiclePapers', 'VehicleRegistrationPapers']),
            'LicenseUrl': _get_flexible_key(row, ['LicenseUrl', 'LicensePaper', 'DriverIdentity', 'Driver License']),
            'LastActive': _get_flexible_key(row, ['LastActive', 'Last Active', 'LastUsed'], 'N/A')
        }
        return clean
    
    if schema_type == 'slots':
        return {
            'SlotID': _get_flexible_key(row, ['SlotID', 'Slot ID']),
            'SlotNumber': _get_flexible_key(row, ['SlotNumber', 'Slot Number', 'Slot No']),
            'Status': _get_flexible_key(row, ['Status', 'Availability'], 'Available')
        }
        
    if schema_type == 'bookings':
        return {
            'BookingID': _get_flexible_key(row, ['BookingID', 'Booking ID']),
            'UserID': _get_flexible_key(row, ['UserID', 'User ID']),
            'SlotID': _get_flexible_key(row, ['SlotID', 'Slot ID']),
            'SlotNumber': _get_flexible_key(row, ['SlotNumber', 'Slot Number']),
            'Date': _get_flexible_key(row, ['Date', 'BookingDate']),
            'Time': _get_flexible_key(row, ['Time', 'BookingTime']),
            'UserName': _get_flexible_key(row, ['UserName', 'User Name']),
            'UserEmail': _get_flexible_key(row, ['UserEmail', 'User Email']),
            'UserStatus': _get_flexible_key(row, ['UserStatus', 'Status', 'BookingStatus']),
            'LoginTime': _get_flexible_key(row, ['LoginTime', 'CheckInTime']),
            'LogoutTime': _get_flexible_key(row, ['LogoutTime', 'CheckOutTime'])
        }
        
    return row


def get_all_users():
    """Get all registered users with data cleaning."""
    try:
        ws = _get_ws('Users')
        records = _get_cached_data('users', lambda: ws.get_all_records())
        return [r for r in [_clean_data_row(row, 'users') for row in records] if r and r.get('UserID')]
    except Exception as e:
        print(f"[ERROR] get_all_users failed: {e}")
        return []

def get_all_slots():
    """Get all parking slots with data cleaning."""
    try:
        ws = _get_ws('ParkingSlots')
        records = _get_cached_data('slots', lambda: ws.get_all_records())
        return [_clean_data_row(row, 'slots') for row in records]
    except Exception as e:
        print(f"[ERROR] get_all_slots failed: {e}")
        return []

def get_all_bookings():
    """Get all bookings with data cleaning."""
    try:
        ws = _get_ws('Bookings')
        records = _get_cached_data('bookings', lambda: ws.get_all_records())
        return [_clean_data_row(row, 'bookings') for row in records]
    except Exception as e:
        print(f"[ERROR] get_all_bookings failed: {e}")
        return []



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
                now = get_ist_now().strftime('%Y-%m-%d %H:%M:%S')
                ws.update_cell(i + 2, 10, now) # LastActive is now column 10
                return True
    except Exception:
        pass  # Non-critical — don't block login if this fails
    return False

# ─── SLOT OPERATIONS ───────────────────────────────────────────

# Replaced by global cleaner above


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
    try:
        user = get_user_by_id(user_id)
        if not user:
            # Re-fetch users without cache once, just in case
            _invalidate('users')
            user = get_user_by_id(user_id)
            if not user:
                print(f"[ERROR] Create booking failed: User {user_id} not found in database.")
                return None

        ws_slots = _get_ws('ParkingSlots')
        # Use cached slots if possible to reduce API calls
        slots = get_all_slots()
        
        target_slot = None
        slot_row_idx = -1
        for i, s in enumerate(slots):
            if str(s.get('SlotID', '')) == str(slot_id) and s.get('Status') == 'Available':
                target_slot = s
                slot_row_idx = i + 2
                break
                
        if not target_slot:
            # Invalidate slots and retry once - maybe someone else booked it
            _invalidate('slots')
            slots = get_all_slots()
            for i, s in enumerate(slots):
                if str(s.get('SlotID', '')) == str(slot_id) and s.get('Status') == 'Available':
                    target_slot = s
                    slot_row_idx = i + 2
                    break
        
        if not target_slot:
            return None
            
        ws_bookings = _get_ws('Bookings')
        booking_id = int(time.time() * 1000)
        now = get_ist_now()
        
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
            
            # Invalidate caches immediately
            _invalidate('bookings', 'slots', 'stats', 'full_dashboard')
            
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
    except Exception as e:
        print(f"[ERROR] create_booking failed: {e}")
        return None

def get_booking_by_id(booking_id):
    """Get booking by ID with cleaning."""
    records = get_all_bookings()
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

# Moved above ^


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
    """Get all data needed for admin dashboard in one go. Using sequential fetch to avoid ThreadPoolExecutor issues on Vercel."""
    try:
        users = get_all_users()
        slots = get_all_slots()
        bookings = get_all_bookings()
        
        available = len([s for s in slots if s.get('Status') == 'Available'])
        parked = len([b for b in bookings if b.get('UserStatus') in ['Logged In', 'Checked In']])
        
        return {
            'stats': {
                'total_users': len(users),
                'total_slots': len(slots),
                'available_slots': available,
                'booked_slots': len(slots) - available if len(slots) > 0 else 0,
                'total_bookings': len(bookings),
                'parked_vehicles': parked
            },
            'slots': slots,
            'bookings': bookings
        }
    except Exception as e:
        print(f"[ERROR] Full dashboard fetch failed: {e}")
        return {
            'stats': {'total_users': 0, 'total_slots': 0, 'available_slots': 0, 'booked_slots': 0, 'total_bookings': 0, 'parked_vehicles': 0},
            'slots': [],
            'bookings': [],
            'error': str(e)
        }

def log_activity(user_id, name, email, action):
    """Log an activity."""
    try:
        ws = _get_ws('ActivityLogs')
        log_id = int(time.time() * 1000)
        now = get_ist_now()
        
        log_data = [
            log_id, user_id, name, email, action,
            now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S')
        ]
        with sheet_lock:
            ws.append_row(log_data)
        return True
    except Exception as e:
        print(f"[ERROR] log_activity failed: {e}")
        return False

def get_all_logs():
    """Get all activity logs."""
    try:
        ws = _get_ws('ActivityLogs')
        return _get_cached_data('logs', lambda: ws.get_all_records())
    except Exception as e:
        print(f"[ERROR] get_all_logs failed: {e}")
        return []

# ─── FEEDBACK OPERATIONS ───────────────────────────────────────

def save_feedback(name, email, rating, feedback_text):
    """Save user feedback."""
    try:
        ws = _get_ws('Feedbacks')
        feedback_id = int(time.time() * 1000)
        now = get_ist_now()
        
        feedback_data = [
            feedback_id, name, email, rating, feedback_text,
            now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'),
            now.isoformat()
        ]
        with sheet_lock:
            ws.append_row(feedback_data)
        return True
    except Exception as e:
        print(f"[ERROR] save_feedback failed: {e}")
        return False

def get_all_feedbacks():
    """Get all user feedbacks."""
    try:
        ws = _get_ws('Feedbacks')
        # We don't cache feedbacks for now as they are less frequent
        records = ws.get_all_records()
        # Ensure 'rating' is an integer for the frontend
        for r in records:
            # Map capitalized headers to lowercase keys for frontend consistency
            r['name'] = r.get('Name')
            r['email'] = r.get('Email')
            r['feedback'] = r.get('Feedback')
            try:
                r['rating'] = int(r.get('Rating', 0))
            except:
                r['rating'] = 0
            
            if 'CreatedAt' in r:
                r['createdAt'] = r['CreatedAt']
                
        return sorted(records, key=lambda x: x.get('CreatedAt', ''), reverse=True)
    except Exception as e:
        print(f"[ERROR] get_all_feedbacks failed: {e}")
        return []

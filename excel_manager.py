"""
Excel Database Manager for Smart Parking System
Handles all CRUD operations on the Excel-based database.
"""

import os
import threading
from openpyxl import Workbook, load_workbook
from datetime import datetime
import config

# Thread lock to prevent concurrent Excel file access
excel_lock = threading.Lock()


def init_excel():
    """Initialize the Excel database with required sheets and default data."""
    if os.path.exists(config.EXCEL_FILE):
        return

    wb = Workbook()

    # Sheet 1: Users
    ws_users = wb.active
    ws_users.title = 'Users'
    ws_users.append(['UserID', 'Name', 'Email', 'Password'])
    # Add a default test user (password: password123)
    from werkzeug.security import generate_password_hash
    ws_users.append([1, 'Test User', 'test@example.com', generate_password_hash('password123')])

    # Sheet 2: ParkingSlots
    ws_slots = wb.create_sheet('ParkingSlots')
    ws_slots.append(['SlotID', 'SlotNumber', 'Status'])
    for i in range(1, config.TOTAL_SLOTS + 1):
        ws_slots.append([i, f'P-{i:03d}', 'Available'])

    # Sheet 3: Bookings
    ws_bookings = wb.create_sheet('Bookings')
    ws_bookings.append(['BookingID', 'UserID', 'SlotID', 'SlotNumber', 'Date', 'Time', 'UserName', 'UserEmail'])

    wb.save(config.EXCEL_FILE)
    print(f"[INFO] Excel database initialized at {config.EXCEL_FILE}")


def _load_workbook():
    """Load the workbook safely. Re-initializes if file is missing."""
    if not os.path.exists(config.EXCEL_FILE):
        print(f"[WARN] Excel file missing at {config.EXCEL_FILE}. Re-initializing...")
        init_excel()
    return load_workbook(config.EXCEL_FILE)


def _save_workbook(wb):
    """Save the workbook safely."""
    wb.save(config.EXCEL_FILE)


# ─── USER OPERATIONS ────────────────────────────────────────────

def get_user_by_email(email):
    """Find a user by email address."""
    with excel_lock:
        wb = _load_workbook()
        ws = wb['Users']
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[2] and row[2].lower() == email.lower():
                return {
                    'UserID': row[0],
                    'Name': row[1],
                    'Email': row[2],
                    'Password': row[3]
                }
        return None


def get_user_by_id(user_id):
    """Find a user by their UserID."""
    with excel_lock:
        wb = _load_workbook()
        ws = wb['Users']
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[0] == user_id:
                return {
                    'UserID': row[0],
                    'Name': row[1],
                    'Email': row[2],
                    'Password': row[3]
                }
        return None


def register_user(name, email, password):
    """Register a new user. Returns the new user dict or None if email exists."""
    with excel_lock:
        wb = _load_workbook()
        ws = wb['Users']

        # Check if email already exists
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[2] and row[2].lower() == email.lower():
                return None

        # Generate new UserID
        max_id = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[0] and isinstance(row[0], int):
                max_id = max(max_id, row[0])
        new_id = max_id + 1

        ws.append([new_id, name, email, password])
        _save_workbook(wb)

        return {
            'UserID': new_id,
            'Name': name,
            'Email': email
        }


def get_all_users():
    """Get all registered users."""
    with excel_lock:
        wb = _load_workbook()
        ws = wb['Users']
        users = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[0]:
                users.append({
                    'UserID': row[0],
                    'Name': row[1],
                    'Email': row[2]
                })
        return users


# ─── PARKING SLOT OPERATIONS ────────────────────────────────────

def get_all_slots():
    """Get all parking slots with their status."""
    with excel_lock:
        wb = _load_workbook()
        ws = wb['ParkingSlots']
        slots = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[0]:
                slots.append({
                    'SlotID': row[0],
                    'SlotNumber': row[1],
                    'Status': row[2]
                })
        return slots


def get_slot_by_id(slot_id):
    """Get a single slot by its ID."""
    with excel_lock:
        wb = _load_workbook()
        ws = wb['ParkingSlots']
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[0] == slot_id:
                return {
                    'SlotID': row[0],
                    'SlotNumber': row[1],
                    'Status': row[2]
                }
        return None


def update_slot_status(slot_id, status):
    """Update the status of a parking slot."""
    with excel_lock:
        wb = _load_workbook()
        ws = wb['ParkingSlots']
        for row in ws.iter_rows(min_row=2):
            if row[0].value == slot_id:
                row[2].value = status
                _save_workbook(wb)
                return True
        return False


def add_slot(slot_number):
    """Add a new parking slot."""
    with excel_lock:
        wb = _load_workbook()
        ws = wb['ParkingSlots']

        # Check if slot number already exists
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[1] == slot_number:
                return None

        # Generate new SlotID
        max_id = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[0] and isinstance(row[0], int):
                max_id = max(max_id, row[0])
        new_id = max_id + 1

        ws.append([new_id, slot_number, 'Available'])
        _save_workbook(wb)
        return {'SlotID': new_id, 'SlotNumber': slot_number, 'Status': 'Available'}


def delete_slot(slot_id):
    """Delete a parking slot (only if Available)."""
    with excel_lock:
        wb = _load_workbook()
        ws = wb['ParkingSlots']
        for idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
            if row[0].value == slot_id:
                if row[2].value == 'Booked':
                    return False
                ws.delete_rows(idx)
                _save_workbook(wb)
                return True
        return False


# ─── BOOKING OPERATIONS ─────────────────────────────────────────

def create_booking(user_id, slot_id):
    """Create a new booking. Returns booking dict or None if slot unavailable."""
    with excel_lock:
        wb = _load_workbook()
        ws_slots = wb['ParkingSlots']
        ws_bookings = wb['Bookings']
        ws_users = wb['Users']

        # Find the slot and check availability
        slot_row = None
        slot_number = None
        for row in ws_slots.iter_rows(min_row=2):
            if row[0].value == slot_id:
                if row[2].value != 'Available':
                    return None  # Slot not available
                slot_row = row
                slot_number = row[1].value
                break

        if not slot_row:
            return None

        # Get user info
        user_name = ''
        user_email = ''
        for row in ws_users.iter_rows(min_row=2, values_only=True):
            if row and row[0] == user_id:
                user_name = row[1]
                user_email = row[2]
                break

        # Mark slot as booked
        slot_row[2].value = 'Booked'

        # Generate new BookingID
        max_id = 0
        for row in ws_bookings.iter_rows(min_row=2, values_only=True):
            if row and row[0] and isinstance(row[0], int):
                max_id = max(max_id, row[0])
        new_id = max_id + 1

        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M:%S')

        ws_bookings.append([new_id, user_id, slot_id, slot_number, date_str, time_str, user_name, user_email])
        _save_workbook(wb)

        return {
            'BookingID': new_id,
            'UserID': user_id,
            'SlotID': slot_id,
            'SlotNumber': slot_number,
            'Date': date_str,
            'Time': time_str,
            'UserName': user_name,
            'UserEmail': user_email
        }


def cancel_booking(booking_id):
    """Cancel a booking and free the slot."""
    with excel_lock:
        wb = _load_workbook()
        ws_bookings = wb['Bookings']
        ws_slots = wb['ParkingSlots']

        for idx, row in enumerate(ws_bookings.iter_rows(min_row=2), start=2):
            if row[0].value == booking_id:
                slot_id = row[2].value

                # Free the slot
                for slot_row in ws_slots.iter_rows(min_row=2):
                    if slot_row[0].value == slot_id:
                        slot_row[2].value = 'Available'
                        break

                ws_bookings.delete_rows(idx)
                _save_workbook(wb)
                return True
        return False


def get_all_bookings():
    """Get all bookings."""
    with excel_lock:
        wb = _load_workbook()
        ws = wb['Bookings']
        bookings = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[0]:
                bookings.append({
                    'BookingID': row[0],
                    'UserID': row[1],
                    'SlotID': row[2],
                    'SlotNumber': row[3],
                    'Date': row[4],
                    'Time': row[5],
                    'UserName': row[6],
                    'UserEmail': row[7]
                })
        return bookings


def get_user_bookings(user_id):
    """Get all bookings for a specific user."""
    with excel_lock:
        wb = _load_workbook()
        ws = wb['Bookings']
        bookings = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[1] == user_id:
                bookings.append({
                    'BookingID': row[0],
                    'UserID': row[1],
                    'SlotID': row[2],
                    'SlotNumber': row[3],
                    'Date': row[4],
                    'Time': row[5],
                    'UserName': row[6],
                    'UserEmail': row[7]
                })
        return bookings


def get_dashboard_stats():
    """Get statistics for the admin dashboard."""
    with excel_lock:
        wb = _load_workbook()

        # Count users
        ws_users = wb['Users']
        total_users = sum(1 for _ in ws_users.iter_rows(min_row=2, values_only=True) if _[0])

        # Count slots
        ws_slots = wb['ParkingSlots']
        total_slots = 0
        available_slots = 0
        booked_slots = 0
        for row in ws_slots.iter_rows(min_row=2, values_only=True):
            if row and row[0]:
                total_slots += 1
                if row[2] == 'Available':
                    available_slots += 1
                else:
                    booked_slots += 1

        # Count bookings
        ws_bookings = wb['Bookings']
        total_bookings = sum(1 for _ in ws_bookings.iter_rows(min_row=2, values_only=True) if _[0])

        return {
            'total_users': total_users,
            'total_slots': total_slots,
            'available_slots': available_slots,
            'booked_slots': booked_slots,
            'total_bookings': total_bookings
        }

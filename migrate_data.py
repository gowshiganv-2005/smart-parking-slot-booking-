import excel_manager
import gsheet_manager as db
import openpyxl
import os

def migrate():
    print("Starting migration from Excel to Google Sheets...")
    
    try:
        # Load local excel data
        excel_manager.init_excel()
        
        # 1. Migrate Users
        print("Migrating Users...")
        # excel_manager.get_all_users() excludes Password, so let's read the raw worksheet
        sh_gs = db._get_client()
        ws_gs = sh_gs.worksheet('Users')
        
        wb_excel = excel_manager._load_workbook()
        ws_excel = wb_excel['Users']
        
        total_users = 0
        import time

        for row in ws_excel.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]: continue
            
            # Pad row if it's shorter than expected
            full_row = list(row) + [None] * (6 - len(row))
            user_id, name, email, password, phone, last_active = full_row[0], full_row[1], full_row[2], full_row[3], full_row[4], full_row[5]
            
            if not db.get_user_by_email(email):
                ws_gs.append_row([user_id, name, email, password, phone or '', last_active or 'N/A'])
                total_users += 1
        print(f"Migrated {total_users} users.")

        # 2. Migrate Slots (Existing slots in Sheet will remain, but let's sync status)
        print("Migrating Slots...")
        excel_slots = excel_manager.get_all_slots()
        for s in excel_slots:
            db.update_slot_status(s['SlotID'], s['Status'])
        print(f"Synced {len(excel_slots)} slots statuses.")

        # 3. Migrate Bookings
        print("Migrating Bookings...")
        excel_bookings = excel_manager.get_all_bookings()
        sh = db._get_client()
        ws = sh.worksheet('Bookings')
        current_bookings = db.get_all_bookings()
        current_ids = [str(b['BookingID']) for b in current_bookings]
        
        added_bookings = 0
        for b in excel_bookings:
            if str(b['BookingID']) not in current_ids:
                ws.append_row([
                    b['BookingID'], b['UserID'], b['SlotID'], b['SlotNumber'],
                    b['Date'], b['Time'], b['UserName'], b['UserEmail'],
                    b.get('UserStatus', 'Pending'), b.get('LoginTime', 'N/A'), b.get('LogoutTime', 'N/A')
                ])
                added_bookings += 1
        print(f"Migrated {added_bookings} bookings.")

        print("Migration complete!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate()

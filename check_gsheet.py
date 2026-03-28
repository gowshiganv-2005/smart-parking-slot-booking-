"""Check what's in the actual Google Sheet 'Users' tab."""
import gsheet_manager as gs
import json

try:
    # This will use the credentials from the filesystem
    sh = gs._get_client()
    ws = gs._get_ws('Users')
    records = ws.get_all_records()
    print(f"Total Google Sheet users: {len(records)}")
    for r in records:
        uid = r.get('UserID', '?')
        name = r.get('Name', '?')
        email = r.get('Email', '?')
        plate = r.get('PlateNumber', 'N/A')
        pwd = str(r.get('Password', ''))[:10]
        print(f"  [{uid}] {name} | {email} | plate={plate} | pwd={pwd}...")
except Exception as e:
    print(f"[ERROR] Could not check Google Sheet: {e}")

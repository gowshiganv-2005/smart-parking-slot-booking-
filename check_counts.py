"""Check the literal row count of the Users sheet."""
import gsheet_manager as gs

try:
    sh = gs._get_client()
    ws = sh.worksheet('Users')
    all_values = ws.get_all_values()
    print(f"Total Rows in GSheet (including header): {len(all_values)}")
    records = ws.get_all_records()
    print(f"Total Records via get_all_records(): {len(records)}")
    if records:
        print(f"First Record Keys: {list(records[0].keys())}")
    
    # Process them like the app does
    users = gs.get_all_users()
    print(f"Total Users after cleaning: {len(users)}")
    
except Exception as e:
    print(f"ERROR: {e}")

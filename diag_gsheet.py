"""Verbose GSheet check."""
import gspread
from google.oauth2.service_account import Credentials
import json
import os

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

f = 'aqueous-cortex-482804-k1-88c2cdf0fee4.json'
try:
    with open(f) as jf:
        info = json.load(jf)
    
    # Check key integrity
    if 'private_key' not in info:
        print("FAIL: private_key missing in JSON")
    else:
        print(f"Key ID: {info.get('private_key_id')}")
        print(f"Project: {info.get('project_id')}")
    
    credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
    gc = gspread.authorize(credentials)
    
    sheet_id = '1ETo_KdLwhE1Y_mhPXCDjwVhe1xFIPeigyx3qvobOrx4'
    sh = gc.open_by_key(sheet_id)
    print(f"SUCCESS: Opened spreadsheet: {sh.title}")
    
    ws = sh.worksheet('Users')
    print(f"User count: {len(ws.get_all_records())}")
    
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

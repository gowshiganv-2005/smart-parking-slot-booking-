import os

# Flask Configuration
SECRET_KEY = os.environ.get('SECRET_KEY', 'smart-parking-secret-key-2026')

# Email Configuration (Update these with your actual credentials)
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_EMAIL = os.environ.get('SMTP_EMAIL', 'your-email@gmail.com')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', 'your-app-password')

# Admin Credentials
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@smartparking.com')

# Parking Configuration
TOTAL_SLOTS = int(os.environ.get('TOTAL_SLOTS', 20))
# Default to local, but prioritize environment variable for production
BASE_URL = os.environ.get('BASE_URL')
if not BASE_URL:
    if os.environ.get('VERCEL') == '1' or os.environ.get('NOW_REGION'):
        # On Vercel, we often rely on the request host, but we can set a placeholder
        BASE_URL = 'https://smart-parking-jeevan.vercel.app' 
    else:
        BASE_URL = 'http://127.0.0.1:5000'

# Google Sheets Configuration
GSHEET_ID = os.environ.get('GSHEET_ID', '1ETo_KdLwhE1Y_mhPXCDjwVhe1xFIPeigyx3qvobOrx4')
# Note: In production, the JSON content is passed via environment variable (GSHEET_CREDENTIALS_JSON).
# Locally, it falls back to this specific file within the same directory.
GSHEET_CREDENTIALS_FILE = os.getenv('GSHEET_CREDENTIALS_FILE', 'smart-parking-db-489314.json')

# Spreadsheet Access Configuration for Vercel
# (Optional: Allows passing credential content as raw JSON in env)
GSHEET_CREDENTIALS_JSON = os.environ.get('GSHEET_CREDENTIALS_JSON')

import sys

# Excel Database Configuration (Fallback)
if (os.environ.get('VERCEL') == '1' or os.environ.get('NOW_REGION')) and not sys.platform.startswith('win'):
    # Vercel serverless environment is read-only except for /tmp
    EXCEL_FILE = '/tmp/parking_data.xlsx'
else:
    EXCEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parking_data.xlsx')

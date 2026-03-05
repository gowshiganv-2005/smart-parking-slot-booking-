import os

# Flask Configuration
SECRET_KEY = os.environ.get('SECRET_KEY', 'smart-parking-secret-key-2026')

# Excel Database Path
# On Vercel, we must use /tmp for writing files
if os.environ.get('VERCEL'):
    EXCEL_FILE = '/tmp/parking_data.xlsx'
else:
    EXCEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parking_data.xlsx')

# Email Configuration (Update these with your actual credentials)
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_EMAIL = os.environ.get('SMTP_EMAIL', 'your-email@gmail.com')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', 'your-app-password')

# Admin Credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@smartparking.com')

# Parking Configuration
TOTAL_SLOTS = 20
BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')

# Google Sheets Configuration
GSHEET_ID = '1ETo_KdLwhE1Y_mhPXCDjwVhe1xFIPeigyx3qvobOrx4'
GSHEET_CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aqueous-cortex-482804-k1-88c2cdf0fee4.json')

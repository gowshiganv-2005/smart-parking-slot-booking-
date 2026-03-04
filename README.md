# 🅿️ Smart Parking Slot Booking System

A full-stack **Smart Parking Slot Booking Web Application** with Admin Panel and User Panel, built with Flask and Excel-based database.

## ✨ Features

### 👤 User Panel
- User registration & login with password hashing
- View available parking slots in a visual grid
- Book parking slots with one-click confirmation
- View & cancel active bookings
- QR code generated for each booking
- Confirmation email with QR code sent automatically
- Real-time slot availability updates (auto-refresh every 10 seconds)

### 🛡️ Admin Panel
- Admin login with secure credentials
- Dashboard with system statistics (total/available/booked slots, users)
- Visual slot overview map
- Manage slots: add new slots, delete available slots
- View & cancel all bookings
- View registered users
- **QR Code Scanner** — scan user QR codes via camera to verify bookings
- Manual QR data entry for fallback verification
- Email notification when users book slots

### 📧 Email System
- Booking confirmation emails to users (with embedded QR code)
- Admin notification emails on new bookings
- Cancellation notification emails
- Beautiful HTML email templates

### 📊 Excel Database
- Microsoft Excel (.xlsx) as backend database
- Thread-safe read/write operations
- Auto-generates on first run with 20 parking slots

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3 (Dark Glassmorphism Theme), JavaScript |
| Backend | Python Flask 3.0 |
| Database | Microsoft Excel via openpyxl |
| Auth | Session-based with Werkzeug password hashing |
| Email | SMTP via smtplib (threaded, non-blocking) |
| QR Code | qrcode + Pillow (generation), html5-qrcode (scanning) |

## 📁 Project Structure

```
├── app.py                    # Flask application & API routes
├── config.py                 # Configuration (SMTP, admin creds)
├── excel_manager.py          # Excel CRUD operations
├── email_service.py          # Email notification system
├── qr_generator.py           # QR code generation
├── requirements.txt          # Python dependencies
├── .gitignore
├── static/
│   ├── css/style.css         # Premium dark-theme stylesheet
│   └── js/
│       ├── auth.js           # Login & registration logic
│       ├── user.js           # User dashboard logic
│       └── admin.js          # Admin dashboard logic
└── templates/
    ├── login.html            # User login page
    ├── register.html         # User registration page
    ├── user_dashboard.html   # User booking dashboard
    ├── admin_login.html      # Admin login page
    └── admin_dashboard.html  # Admin management panel
```

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/gowshiganv-2005/smart-parking-slot-booking-.git
cd smart-parking-slot-booking-

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

### Access the Application

| Panel | URL |
|-------|-----|
| User Login | http://127.0.0.1:5000/login |
| User Registration | http://127.0.0.1:5000/register |
| Admin Login | http://127.0.0.1:5000/admin |

### Default Admin Credentials
- **Username:** `admin`
- **Password:** `admin123`

## 📧 Email Configuration

To enable email notifications, update `config.py`:

```python
SMTP_EMAIL = 'your-email@gmail.com'
SMTP_PASSWORD = 'your-app-password'
ADMIN_EMAIL = 'admin@example.com'
```

For Gmail, generate an [App Password](https://myaccount.google.com/apppasswords).

## 📸 Screenshots

### User Login
![Login Page](screenshots/login.png)

### User Dashboard
![User Dashboard](screenshots/user_dashboard.png)

### Admin Dashboard
![Admin Dashboard](screenshots/admin_dashboard.png)

### QR Scanner
![QR Scanner](screenshots/qr_scanner.png)

## 📄 Excel Database Schema

| Sheet | Columns |
|-------|---------|
| Users | UserID, Name, Email, Password |
| ParkingSlots | SlotID, SlotNumber, Status |
| Bookings | BookingID, UserID, SlotID, SlotNumber, Date, Time, UserName, UserEmail |

## 📝 License

This project is for educational purposes.

---

**Built with ❤️ by Gowshigan V**

"""
Email Notification Service for Smart Parking System
Sends booking confirmation emails to users and notification emails to admin.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import config
from qr_generator import get_qr_data_uri


from email.mime.image import MIMEImage
import base64
import io

def _send_email(to_email, subject, html_body, attachment_img=None):
    """Send an email in a background thread to avoid blocking requests."""
    def _send():
        server = None
        try:
            msg = MIMEMultipart('related')
            msg['From'] = config.SMTP_EMAIL
            msg['To'] = to_email
            msg['Subject'] = subject

            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)
            msg_alternative.attach(MIMEText(html_body, 'html'))

            if attachment_img:
                # attachment_img is expected to be a data URI: data:image/png;base64,...
                header, encoded = attachment_img.split(",", 1)
                img_data = base64.b64decode(encoded)
                mime_img = MIMEImage(img_data)
                mime_img.add_header('Content-ID', '<qr_code>')
                mime_img.add_header('Content-Disposition', 'inline', filename='qr_code.png')
                msg.attach(mime_img)

            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
            server.starttls()
            server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()

            print(f"[EMAIL] Successfully sent to {to_email}")
        except Exception as e:
            print(f"[EMAIL ERROR] Failed to send to {to_email}: {str(e)}")
        finally:
            if server:
                try:
                    server.quit()
                except Exception as e:
                    pass


    thread = threading.Thread(target=_send)
    thread.daemon = True
    thread.start()


def send_booking_confirmation(user_email, user_name, booking):
    """Send booking confirmation email to the user with QR code."""
    # Generate QR code for the booking
    qr_data_uri = get_qr_data_uri(booking)

    subject = f"🅿️ Parking Booking Confirmed - Slot {booking['SlotNumber']}"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; background: #f0f2f5; }}
            .container {{ max-width: 600px; margin: 30px auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 30px; text-align: center; color: white; }}
            .header h1 {{ margin: 0; font-size: 28px; letter-spacing: 1px; }}
            .header p {{ margin: 10px 0 0; opacity: 0.9; font-size: 16px; }}
            .body {{ padding: 30px; }}
            .greeting {{ font-size: 18px; color: #333; margin-bottom: 20px; }}
            .details {{ background: #f8f9ff; border-radius: 12px; padding: 24px; margin: 20px 0; border-left: 4px solid #667eea; }}
            .detail-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e8e8f0; }}
            .detail-row:last-child {{ border-bottom: none; }}
            .detail-label {{ color: #666; font-weight: 600; }}
            .detail-value {{ color: #333; font-weight: 700; }}
            .footer {{ text-align: center; padding: 20px 30px; color: #999; font-size: 13px; background: #fafafa; }}
            .badge {{ display: inline-block; background: #22c55e; color: white; padding: 6px 16px; border-radius: 20px; font-size: 14px; font-weight: 600; margin-top: 10px; }}
            .qr-section {{ text-align: center; margin: 30px 0 10px; padding: 24px; background: #f8f9ff; border-radius: 12px; }}
            .qr-section img {{ width: 200px; height: 200px; border-radius: 12px; border: 3px solid #667eea; }}
            .qr-section p {{ color: #666; font-size: 13px; margin-top: 12px; }}
            .qr-section h3 {{ color: #333; font-size: 16px; margin-bottom: 16px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🅿️ Smart Parking</h1>
                <p>Booking Confirmation</p>
            </div>
            <div class="body">
                <p class="greeting">Hello <strong>{user_name}</strong>,</p>
                <p>Your parking slot has been successfully booked! Here are your booking details:</p>
                <div class="details">
                    <div class="detail-row">
                        <span class="detail-label">Booking ID</span>
                        <span class="detail-value">#{booking['BookingID']}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Slot Number</span>
                        <span class="detail-value">{booking['SlotNumber']}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Date</span>
                        <span class="detail-value">{booking['Date']}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Time</span>
                        <span class="detail-value">{booking['Time']}</span>
                    </div>
                </div>
                <div style="text-align: center;">
                    <span class="badge">✓ Confirmed</span>
                </div>
                <div class="qr-section">
                    <h3>📱 Your Booking QR Code</h3>
                    <img src="cid:qr_code" alt="Booking QR Code" />
                    <p>Present this QR code at the parking entrance.<br/>The admin will scan it to verify your booking.</p>
                </div>
            </div>
            <div class="footer">
                <p>© 2026 Smart Parking System | All Rights Reserved</p>
            </div>
        </div>
    </body>
    </html>
    """
    _send_email(user_email, subject, html_body, attachment_img=qr_data_uri)


def send_admin_notification(booking):
    """Send notification email to admin when a new booking is made."""
    subject = f"📋 New Booking Alert - Slot {booking['SlotNumber']} Booked"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; background: #f0f2f5; }}
            .container {{ max-width: 600px; margin: 30px auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #f97316 0%, #ef4444 100%); padding: 40px 30px; text-align: center; color: white; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .header p {{ margin: 10px 0 0; opacity: 0.9; }}
            .body {{ padding: 30px; }}
            .details {{ background: #fff7ed; border-radius: 12px; padding: 24px; margin: 20px 0; border-left: 4px solid #f97316; }}
            .detail-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #fee2c5; }}
            .detail-row:last-child {{ border-bottom: none; }}
            .detail-label {{ color: #666; font-weight: 600; }}
            .detail-value {{ color: #333; font-weight: 700; }}
            .footer {{ text-align: center; padding: 20px 30px; color: #999; font-size: 13px; background: #fafafa; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📋 Admin Alert</h1>
                <p>New Parking Slot Booking</p>
            </div>
            <div class="body">
                <p>A new parking slot has been booked. Here are the details:</p>
                <div class="details">
                    <div class="detail-row">
                        <span class="detail-label">Booking ID</span>
                        <span class="detail-value">#{booking['BookingID']}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">User</span>
                        <span class="detail-value">{booking['UserName']}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Email</span>
                        <span class="detail-value">{booking['UserEmail']}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Slot</span>
                        <span class="detail-value">{booking['SlotNumber']}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Date</span>
                        <span class="detail-value">{booking['Date']}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Time</span>
                        <span class="detail-value">{booking['Time']}</span>
                    </div>
                </div>
            </div>
            <div class="footer">
                <p>© 2026 Smart Parking System — Admin Panel</p>
            </div>
        </div>
    </body>
    </html>
    """
    _send_email(config.ADMIN_EMAIL, subject, html_body)


def send_cancellation_email(user_email, user_name, slot_number):
    """Send booking cancellation email to the user."""
    subject = f"🅿️ Parking Booking Cancelled - Slot {slot_number}"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; background: #f0f2f5; }}
            .container {{ max-width: 600px; margin: 30px auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 40px 30px; text-align: center; color: white; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .body {{ padding: 30px; text-align: center; }}
            .footer {{ text-align: center; padding: 20px 30px; color: #999; font-size: 13px; background: #fafafa; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Booking Cancelled</h1>
            </div>
            <div class="body">
                <p>Hello <strong>{user_name}</strong>,</p>
                <p>Your booking for slot <strong>{slot_number}</strong> has been cancelled.</p>
                <p>The slot is now available for rebooking.</p>
            </div>
            <div class="footer">
                <p>© 2026 Smart Parking System | All Rights Reserved</p>
            </div>
        </div>
    </body>
    </html>
    """
    _send_email(user_email, subject, html_body)

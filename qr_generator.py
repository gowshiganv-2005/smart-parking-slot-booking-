"""
QR Code Generator for Smart Parking System
Generates QR codes containing booking information.
"""

import qrcode
import io
import base64
import json


def generate_booking_qr(booking):
    """
    Generate a QR code containing booking details.
    Returns a base64-encoded PNG image string.
    """
    import config
    # Generate the access URL
    access_url = f"{config.BASE_URL}/parking-access?booking_id={booking['BookingID']}"

    # Encode booking data as JSON or just the URL
    # The requirement says QR should open a special webpage, so many scanners 
    # will automatically open the URL if it's the primary data.
    qr_data = access_url

    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    # Generate image with custom colors
    img = qr.make_image(fill_color="#1a1040", back_color="#ffffff")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return img_base64


def get_qr_data_uri(booking):
    """Returns a data URI for embedding QR code in HTML/emails."""
    img_base64 = generate_booking_qr(booking)
    return f"data:image/png;base64,{img_base64}"

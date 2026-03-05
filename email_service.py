from flask_mail import Message
import threading

# We will initialize mail in app.py and import it here
# But to avoid circular imports, we might need a better way.
# Standard practice is to have a mail object in a separate file or pass it.

def send_email_async(app, msg, mail):
    with app.app_context():
        mail.send(msg)

def send_booking_confirmation(app, mail, user_email, user_name, slot_number, booking_id, booking_date, booking_time):
    msg = Message(f"🅿️ Parking Slot Confirmation - Slot {slot_number}",
                  recipients=[user_email])
    
    msg.html = f"""
    <h3>Hello {user_name},</h3>
    <p>Your parking slot <strong>{slot_number}</strong> has been successfully booked.</p>
    <p><strong>Booking ID:</strong> #{booking_id}</p>
    <p><strong>Date:</strong> {booking_date}</p>
    <p><strong>Time:</strong> {booking_time}</p>
    <br>
    <p>Thank you for using Smart Parking System.</p>
    """
    
    thread = threading.Thread(target=send_email_async, args=(app, msg, mail))
    thread.start()

def send_cancellation_email(app, mail, user_email, user_name, slot_number):
    msg = Message(f"🅿️ Parking Slot Cancellation - Slot {slot_number}",
                  recipients=[user_email])
    
    msg.html = f"""
    <h3>Hello {user_name},</h3>
    <p>Your booking for slot <strong>{slot_number}</strong> has been cancelled.</p>
    <br>
    <p>Thank you for using Smart Parking System.</p>
    """
    
    thread = threading.Thread(target=send_email_async, args=(app, msg, mail))
    thread.start()

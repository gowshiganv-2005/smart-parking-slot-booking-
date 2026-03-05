from database.mongodb import db
from datetime import datetime
from bson import ObjectId

class Booking:
    @staticmethod
    def create_booking(user_id, slot_id, booking_date, start_time, end_time):
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        if isinstance(slot_id, str):
            slot_id = ObjectId(slot_id)
            
        booking_data = {
            "user_id": user_id,
            "slot_id": slot_id,
            "booking_date": booking_date,
            "start_time": start_time,
            "end_time": end_time,
            "status": "active",
            "created_at": datetime.utcnow()
        }
        return db.bookings.insert_one(booking_data)

    @staticmethod
    def get_user_bookings(user_id):
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        return list(db.bookings.find({"user_id": user_id}).sort("created_at", -1))

    @staticmethod
    def get_all_bookings():
        return list(db.bookings.find().sort("created_at", -1))

    @staticmethod
    def cancel_booking(booking_id):
        if isinstance(booking_id, str):
            booking_id = ObjectId(booking_id)
        booking = db.bookings.find_one({"_id": booking_id})
        if booking:
            db.bookings.update_one({"_id": booking_id}, {"$set": {"status": "cancelled"}})
            return booking
        return None

    @staticmethod
    def get_booking_by_id(booking_id):
        if isinstance(booking_id, str):
            booking_id = ObjectId(booking_id)
        return db.bookings.find_one({"_id": booking_id})

from database.mongodb import db
from datetime import datetime
from bson import ObjectId

class ParkingSlot:
    @staticmethod
    def init_slots(total_slots):
        if db.parking_slots.count_documents({}) == 0:
            slots = []
            for i in range(1, total_slots + 1):
                slots.append({
                    "slot_number": i,
                    "status": "available",
                    "booked_by": None,
                    "booking_time": None
                })
            db.parking_slots.insert_many(slots)

    @staticmethod
    def get_all_slots():
        return list(db.parking_slots.find().sort("slot_number", 1))

    @staticmethod
    def get_slot_by_id(slot_id):
        if isinstance(slot_id, str):
            slot_id = ObjectId(slot_id)
        return db.parking_slots.find_one({"_id": slot_id})

    @staticmethod
    def get_slot_by_number(slot_number):
        return db.parking_slots.find_one({"slot_number": int(slot_number)})

    @staticmethod
    def update_status(slot_id, status, user_id=None):
        if isinstance(slot_id, str):
            slot_id = ObjectId(slot_id)
        update_data = {
            "status": status,
            "booked_by": user_id,
            "booking_time": datetime.utcnow() if status == "booked" else None
        }
        db.parking_slots.update_one({"_id": slot_id}, {"$set": update_data})

    @staticmethod
    def add_slot(slot_number):
        if db.parking_slots.find_one({"slot_number": int(slot_number)}):
            return None
        return db.parking_slots.insert_one({
            "slot_number": int(slot_number),
            "status": "available",
            "booked_by": None,
            "booking_time": None
        })

    @staticmethod
    def delete_slot(slot_id):
        if isinstance(slot_id, str):
            slot_id = ObjectId(slot_id)
        slot = db.parking_slots.find_one({"_id": slot_id})
        if slot and slot["status"] == "available":
            db.parking_slots.delete_one({"_id": slot_id})
            return True
        return False

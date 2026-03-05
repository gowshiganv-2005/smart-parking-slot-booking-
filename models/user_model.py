from database.mongodb import db
from datetime import datetime
from bson import ObjectId

class User:
    @staticmethod
    def create_user(name, email, password, role="user"):
        user_data = {
            "name": name,
            "email": email,
            "password": password, # Should be hashed before calling
            "role": role,
            "created_at": datetime.utcnow()
        }
        return db.users.insert_one(user_data)

    @staticmethod
    def get_by_email(email):
        return db.users.find_one({"email": email})

    @staticmethod
    def get_by_id(user_id):
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        return db.users.find_one({"_id": user_id})

    @staticmethod
    def get_all_users():
        return list(db.users.find({}, {"password": 0}))

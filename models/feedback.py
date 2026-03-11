from datetime import datetime
import os
from dotenv import load_dotenv

try:
    from pymongo import MongoClient
except ImportError:
    # If pymongo is not installed, we can suggest it
    MongoClient = None

load_dotenv()

class FeedbackModel:
    def __init__(self):
        if MongoClient:
            self.client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'))
            self.db = self.client[os.getenv('DB_NAME', 'smart_parking')]
            self.collection = self.db['feedbacks']
        else:
            self.collection = None

    def save_feedback(self, name, email, rating, feedback_text):
        if not self.collection:
            print("[ERROR] MongoDB not connected. Please install pymongo.")
            return False
            
        feedback_data = {
            "name": name,
            "email": email,
            "rating": rating,
            "feedback": feedback_text,
            "createdAt": datetime.utcnow()
        }
        
        try:
            result = self.collection.insert_one(feedback_data)
            return True if result.inserted_id else False
        except Exception as e:
            print(f"[ERROR] Failed to save feedback to MongoDB: {e}")
            return False

    def get_all_feedbacks(self):
        if not self.collection:
            return []
        try:
            feedbacks = list(self.collection.find().sort("createdAt", -1))
            # Convert ObjectId and datetime to serializable format
            for f in feedbacks:
                f['_id'] = str(f['_id'])
                if isinstance(f.get('createdAt'), datetime):
                    f['createdAt'] = f['createdAt'].isoformat()
            return feedbacks
        except Exception as e:
            print(f"[ERROR] Failed to fetch feedbacks: {e}")
            return []

feedback_db = FeedbackModel()

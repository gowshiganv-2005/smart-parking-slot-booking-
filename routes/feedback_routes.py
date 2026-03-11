from flask import Blueprint, request, jsonify
from models.feedback import feedback_db

feedback_bp = Blueprint('feedback', __name__)

@feedback_bp.route('/api/feedback', methods=['POST'])
def add_feedback():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        rating = data.get('rating')
        feedback_text = data.get('feedback', '').strip()

        # Validation
        if not all([name, email, rating, feedback_text]):
            return jsonify({
                'success': False, 
                'message': 'All fields are required'
            }), 400

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError
        except:
            return jsonify({
                'success': False, 
                'message': 'Rating must be a number between 1 and 5'
            }), 400

        # Save to MongoDB
        success = feedback_db.save_feedback(name, email, rating, feedback_text)

        if success:
            return jsonify({
                'success': True, 
                'message': 'Feedback submitted successfully'
            }), 201
        else:
            return jsonify({
                'success': False, 
                'message': 'Could not save feedback. Ensure MongoDB is running.'
            }), 500

    except Exception as e:
        print(f"[ERROR] Feedback API Error: {e}")
        return jsonify({
            'success': False, 
            'message': 'Internal Server Error'
        }), 500

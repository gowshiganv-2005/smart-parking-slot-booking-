from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from models.user_model import User
import bcrypt
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')

        if User.get_by_email(email):
            return jsonify({"success": False, "message": "Email already exists"}), 400

        hashed_pw = hash_password(password)
        User.create_user(name, email, hashed_pw)
        return jsonify({"success": True, "message": "Registration successful"})
    
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        user = User.get_by_email(email)
        if user and check_password(password, user['password']):
            session['user_id'] = str(user['_id'])
            session['user_name'] = user['name']
            session['role'] = user['role']
            return jsonify({"success": True, "message": "Login successful", "role": user['role']})
        
        return jsonify({"success": False, "message": "Invalid email or password"}), 401
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

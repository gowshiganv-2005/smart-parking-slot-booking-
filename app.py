from flask import Flask, render_template, redirect, url_for, session
from flask_mail import Mail
from database.mongodb import db
from models.parking_model import ParkingSlot
from models.user_model import User
from routes.auth_routes import auth_bp
from routes.user_routes import user_bp
from routes.admin_routes import admin_bp
import config
import os
import bcrypt

app = Flask(__name__)
app.config.from_object(config)
app.secret_key = config.SECRET_KEY

# Flask-Mail configuration
app.config['MAIL_SERVER'] = config.SMTP_SERVER
app.config['MAIL_PORT'] = config.SMTP_PORT
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = config.SMTP_EMAIL
app.config['MAIL_PASSWORD'] = config.SMTP_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = config.SMTP_EMAIL

mail = Mail(app)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(admin_bp)

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('user.dashboard'))
    return redirect(url_for('auth.login'))

def init_app():
    # Initialize parking slots
    ParkingSlot.init_slots(config.TOTAL_SLOTS)
    
    # Create default admin if not exists
    if not User.get_by_email(config.ADMIN_EMAIL):
        hashed_pw = bcrypt.hashpw(config.ADMIN_PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        User.create_user("Admin", config.ADMIN_EMAIL, hashed_pw, role="admin")
        print(f"[INFO] Default admin created: {config.ADMIN_EMAIL}")

if __name__ == '__main__':
    with app.app_context():
        init_app()
    app.run(debug=True, port=5000)

"""
Cafe Ubud — Flask Application Factory
=======================================
Environment variables:
  SECRET_KEY       - Flask session signing key
  DATABASE_URL     - DB connection string (defaults to local SQLite)
  TWILIO_SID       - Twilio Account SID (for WhatsApp)
  TWILIO_TOKEN     - Twilio Auth Token
  TWILIO_FROM      - Twilio WhatsApp number e.g. whatsapp:+14155238886
  RAZORPAY_KEY_ID  - Razorpay key id
  RAZORPAY_SECRET  - Razorpay key secret
  ADMIN_USERNAME   - admin login username (default: admin)
  ADMIN_PASSWORD   - admin login password (auto-generated if not set)
"""

import os
from flask import Flask
from flask_socketio import SocketIO
from models import db

socketio = SocketIO(cors_allowed_origins="*")


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    # Upload folder for menu item images
    upload_folder = os.path.join(app.instance_path, "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    print(f"Upload folder: {upload_folder}")  # shows path in terminal on startup
    default_db_uri = f"sqlite:///{os.path.join(app.instance_path, 'cafeubud.db')}"

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", default_db_uri),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JSON_SORT_KEYS=False,
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,   # 8 MB max upload
        UPLOAD_FOLDER=upload_folder,
        ALLOWED_EXTENSIONS={"png", "jpg", "jpeg", "webp", "gif"},
    )

    db.init_app(app)
    socketio.init_app(app)

    from routes.public import public_bp
    from routes.api import api_bp
    from routes.admin import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    return app


if __name__ == "__main__":
    app = create_app()
    socketio.run(app, debug=True, port=5000)

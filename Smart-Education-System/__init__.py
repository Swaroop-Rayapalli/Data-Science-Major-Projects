from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

db       = SQLAlchemy()
login_manager = LoginManager()
mail     = Mail()
bcrypt   = Bcrypt()


def create_app():
    app = Flask(__name__)

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # ── Database: Neon PostgreSQL ─────────────────────────────────────────────
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        db_url = f"sqlite:///{os.path.join(BASE_DIR, 'database', 'smart_education.db')}"
        print("[DB] DATABASE_URL not found — using local SQLite fallback.")
    else:
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        # Strip channel_binding param — psycopg2 does NOT support it; sslmode=require is enough
        db_url = db_url.replace('&channel_binding=require', '').replace('channel_binding=require&', '').replace('channel_binding=require', '').rstrip('?&')
        print("[DB] Connected to Neon PostgreSQL.")

    app.config['SECRET_KEY']                  = os.environ.get('SECRET_KEY', 'smart-edu-secret-2024')
    app.config['SQLALCHEMY_DATABASE_URI']     = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS']   = {
        'pool_pre_ping': True,
        'pool_recycle':  300,
        'connect_args':  {
            'sslmode': 'require',
            # Note: channel_binding is NOT a valid psycopg2 connect_arg — removed
        } if 'neon.tech' in db_url else {}
    }
    app.config['UPLOAD_FOLDER']       = os.path.join(BASE_DIR, 'uploads')
    app.config['MAX_CONTENT_LENGTH']  = 16 * 1024 * 1024

    # ── Gmail SMTP for OTP emails ─────────────────────────────────────────────
    app.config['MAIL_SERVER']        = 'smtp.gmail.com'
    app.config['MAIL_PORT']          = 587
    app.config['MAIL_USE_TLS']       = True
    app.config['MAIL_USERNAME']      = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD']      = os.environ.get('MAIL_PASSWORD', '').replace(' ', '')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

    # ── Flask-Login ───────────────────────────────────────────────────────────
    login_manager.login_view          = 'auth.login'
    login_manager.login_message       = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # Ensure upload directory exists
    os.makedirs(os.path.join(BASE_DIR, 'uploads'), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    bcrypt.init_app(app)

    # User loader for Flask-Login
    with app.app_context():
        from database.models import (
            User, OTPCode,
            StudentPrediction, FeedbackAnalysis, ResumeResult  # noqa: F401
        )
        try:
            db.create_all()
            print("[DB] All tables created/verified.")
        except Exception as e:
            # Don't crash the app on startup if DB is temporarily unavailable
            print(f"[DB] Warning: db.create_all() failed: {e}")

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))

    # Register blueprints
    from routes.auth      import auth_bp
    from routes.student   import student_bp
    from routes.sentiment import sentiment_bp
    from routes.resume    import resume_bp
    from routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp,      url_prefix='/auth')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(student_bp,   url_prefix='/student')
    app.register_blueprint(sentiment_bp, url_prefix='/sentiment')
    app.register_blueprint(resume_bp,    url_prefix='/resume')

    return app

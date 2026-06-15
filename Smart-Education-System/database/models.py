from __init__ import db
from flask_login import UserMixin
from datetime import datetime, timezone


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_verified   = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to OTP codes
    otp_codes = db.relationship('OTPCode', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.email}>'


class OTPCode(db.Model):
    __tablename__ = 'otp_codes'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    code       = db.Column(db.String(6), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used       = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_valid(self):
        """Check if OTP is still valid (not expired, not used)."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return not self.used and self.expires_at > now


class StudentPrediction(db.Model):
    __tablename__ = 'student_predictions'

    id               = db.Column(db.Integer, primary_key=True)
    student_name     = db.Column(db.String(100), nullable=False)
    hours_studied    = db.Column(db.Float, nullable=False)
    previous_scores  = db.Column(db.Float, nullable=False)
    extracurricular  = db.Column(db.Integer, default=0)
    sleep_hours      = db.Column(db.Float, nullable=False)
    sample_papers    = db.Column(db.Integer, nullable=False)
    predicted_score  = db.Column(db.Float, nullable=False)
    risk_level       = db.Column(db.String(20), nullable=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'student_name': self.student_name,
            'hours_studied': self.hours_studied,
            'previous_scores': self.previous_scores,
            'extracurricular': self.extracurricular,
            'sleep_hours': self.sleep_hours,
            'sample_papers': self.sample_papers,
            'predicted_score': round(self.predicted_score, 2),
            'risk_level': self.risk_level,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }


class FeedbackAnalysis(db.Model):
    __tablename__ = 'feedback_analysis'

    id           = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=True)
    feedback     = db.Column(db.Text, nullable=False)
    sentiment    = db.Column(db.String(20), nullable=False)
    confidence   = db.Column(db.Float, default=0.0)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'student_name': self.student_name,
            'feedback': self.feedback,
            'sentiment': self.sentiment,
            'confidence': round(self.confidence * 100, 1),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }


class ResumeResult(db.Model):
    __tablename__ = 'resume_results'

    id                    = db.Column(db.Integer, primary_key=True)
    candidate_name        = db.Column(db.String(100), nullable=False)
    filename              = db.Column(db.String(255), nullable=True)
    category              = db.Column(db.String(100), nullable=False)
    match_score           = db.Column(db.Float, default=0.0)
    extracted_text_preview= db.Column(db.Text, nullable=True)
    created_at            = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'candidate_name': self.candidate_name,
            'filename': self.filename,
            'category': self.category,
            'match_score': round(self.match_score, 1),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }

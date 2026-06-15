from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import random
import string

auth_bp = Blueprint('auth', __name__)


def _get_extensions():
    """Import extensions lazily to avoid circular imports."""
    from __init__ import db, bcrypt, mail
    return db, bcrypt, mail


def generate_otp():
    """Generate a 6-digit OTP code."""
    return ''.join(random.choices(string.digits, k=6))


def send_otp_email(mail, user_email, user_name, otp_code):
    """Send OTP email via Gmail SMTP."""
    from flask_mail import Message
    msg = Message(
        subject='🔐 Your EduAI Verification Code',
        sender=('EduAI Platform', mail.default_sender or 'noreply@eduai.com'),
        recipients=[user_email]
    )
    msg.html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: 'Inter', Arial, sans-serif; background: #0f172a; color: #e2e8f0; margin:0; padding:20px;">
      <div style="max-width:480px; margin:0 auto; background:#1e293b; border-radius:16px; overflow:hidden; border:1px solid #334155;">
        <!-- Header -->
        <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6); padding:32px; text-align:center;">
          <div style="font-size:40px; margin-bottom:8px;">🎓</div>
          <h1 style="margin:0; font-size:22px; font-weight:700; color:#fff;">EduAI Platform</h1>
          <p style="margin:6px 0 0; color:rgba(255,255,255,0.8); font-size:13px;">Smart Education Analytics</p>
        </div>
        <!-- Body -->
        <div style="padding:32px;">
          <p style="color:#94a3b8; margin:0 0 8px;">Hello, <strong style="color:#e2e8f0;">{user_name}</strong> 👋</p>
          <p style="color:#94a3b8; margin:0 0 24px; font-size:14px;">Use the verification code below to complete your registration:</p>
          <!-- OTP Box -->
          <div style="background:#0f172a; border:2px solid #6366f1; border-radius:12px; padding:24px; text-align:center; margin-bottom:24px;">
            <div style="font-size:42px; font-weight:800; letter-spacing:12px; color:#818cf8; font-family:monospace;">{otp_code}</div>
            <p style="color:#64748b; font-size:12px; margin:12px 0 0;">This code expires in <strong style="color:#f59e0b;">10 minutes</strong></p>
          </div>
          <div style="background:#1a2744; border-left:4px solid #f59e0b; border-radius:4px; padding:12px 16px; margin-bottom:24px;">
            <p style="color:#fbbf24; font-size:12px; margin:0;">⚠️ If you did not request this, please ignore this email.</p>
          </div>
        </div>
        <!-- Footer -->
        <div style="background:#0f172a; padding:20px; text-align:center; border-top:1px solid #334155;">
          <p style="color:#475569; font-size:11px; margin:0;">© 2025 EduAI Smart Analytics Platform</p>
        </div>
      </div>
    </body>
    </html>
    """
    mail.send(msg)


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    from database.models import User, OTPCode
    db, bcrypt, mail = _get_extensions()

    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        # Validation
        if not name or not email or not password:
            flash('All fields are required.', 'warning')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'warning')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists. Please log in.', 'warning')
            return redirect(url_for('auth.login'))

        # Create user (unverified)
        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(name=name, email=email, password_hash=pw_hash, is_verified=False)
        db.session.add(user)
        db.session.commit()

        # Generate and save OTP
        otp_code  = generate_otp()
        expires   = datetime.utcnow() + timedelta(minutes=10)
        otp_entry = OTPCode(user_id=user.id, code=otp_code, expires_at=expires)
        db.session.add(otp_entry)
        db.session.commit()

        # Send OTP email
        try:
            send_otp_email(mail, email, name, otp_code)
            flash(f'Verification code sent to {email}. Check your inbox (and spam folder).', 'success')
        except Exception as e:
            flash(f'Account created but email failed: {str(e)}. Contact admin.', 'warning')

        # Store email in session for OTP verification step
        session['pending_verify_email'] = email
        return redirect(url_for('auth.verify_otp'))

    return render_template('auth/register.html')


# ─────────────────────────────────────────────────────────────────────────────
# VERIFY OTP
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    from database.models import User, OTPCode
    db, bcrypt, mail = _get_extensions()

    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    email = session.get('pending_verify_email')
    if not email:
        flash('Session expired. Please register again.', 'warning')
        return redirect(url_for('auth.register'))

    user = User.query.filter_by(email=email).first()
    if not user:
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        action = request.form.get('action', 'verify')

        # ── Resend OTP ──
        if action == 'resend':
            # Invalidate old OTPs
            OTPCode.query.filter_by(user_id=user.id, used=False).update({'used': True})
            db.session.commit()

            otp_code  = generate_otp()
            expires   = datetime.utcnow() + timedelta(minutes=10)
            otp_entry = OTPCode(user_id=user.id, code=otp_code, expires_at=expires)
            db.session.add(otp_entry)
            db.session.commit()

            try:
                send_otp_email(mail, email, user.name, otp_code)
                flash('New verification code sent!', 'success')
            except Exception as e:
                flash(f'Failed to resend email: {str(e)}', 'danger')

            return redirect(url_for('auth.verify_otp'))

        # ── Verify OTP ──
        entered = request.form.get('otp', '').strip()
        if not entered or len(entered) != 6:
            flash('Please enter the 6-digit code.', 'warning')
            return render_template('auth/verify_otp.html', email=email)

        latest_otp = OTPCode.query.filter_by(user_id=user.id, used=False)\
                                   .order_by(OTPCode.created_at.desc()).first()

        if not latest_otp:
            flash('No active OTP found. Please request a new one.', 'danger')
            return render_template('auth/verify_otp.html', email=email)

        if not latest_otp.is_valid():
            flash('OTP has expired. Please request a new code.', 'danger')
            return render_template('auth/verify_otp.html', email=email)

        if latest_otp.code != entered:
            flash('Incorrect code. Please try again.', 'danger')
            return render_template('auth/verify_otp.html', email=email)

        # Mark OTP used, verify user
        latest_otp.used   = True
        user.is_verified  = True
        db.session.commit()

        session.pop('pending_verify_email', None)
        flash('✅ Email verified successfully! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/verify_otp.html', email=email)


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    from database.models import User
    db, bcrypt, mail = _get_extensions()

    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(email=email).first()

        if not user or not bcrypt.check_password_hash(user.password_hash, password):
            flash('Invalid email or password.', 'danger')
            return render_template('auth/login.html')

        if not user.is_verified:
            session['pending_verify_email'] = email
            flash('Please verify your email first. A new code has been sent.', 'warning')
            # Auto-resend OTP
            from database.models import OTPCode
            otp_code  = generate_otp()
            expires   = datetime.utcnow() + timedelta(minutes=10)
            OTPCode.query.filter_by(user_id=user.id, used=False).update({'used': True})
            otp_entry = OTPCode(user_id=user.id, code=otp_code, expires_at=expires)
            db.session.add(otp_entry)
            db.session.commit()
            try:
                send_otp_email(mail, email, user.name, otp_code)
            except Exception:
                pass
            return redirect(url_for('auth.verify_otp'))

        login_user(user, remember=remember)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard.index'))

    return render_template('auth/login.html')


# ─────────────────────────────────────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# ─────────────────────────────────────────────────────────────────────────────
# FORGOT PASSWORD — step 1: enter email, receive reset OTP
# ─────────────────────────────────────────────────────────────────────────────
def send_reset_email(mail, user_email, user_name, otp_code):
    from flask_mail import Message
    msg = Message(
        subject='🔑 EduAI Password Reset Code',
        sender=('EduAI Platform', mail.default_sender or 'noreply@eduai.com'),
        recipients=[user_email]
    )
    msg.html = f"""<!DOCTYPE html><html><body style="font-family:'Inter',Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:20px;">
      <div style="max-width:480px;margin:0 auto;background:#1e293b;border-radius:16px;overflow:hidden;border:1px solid #334155;">
        <div style="background:linear-gradient(135deg,#f59e0b,#ef4444);padding:32px;text-align:center;">
          <div style="font-size:40px;margin-bottom:8px;">🔑</div>
          <h1 style="margin:0;font-size:22px;font-weight:700;color:#fff;">Password Reset</h1>
          <p style="margin:6px 0 0;color:rgba(255,255,255,0.8);font-size:13px;">EduAI Smart Analytics Platform</p>
        </div>
        <div style="padding:32px;">
          <p style="color:#94a3b8;margin:0 0 8px;">Hello, <strong style="color:#e2e8f0;">{user_name}</strong> 👋</p>
          <p style="color:#94a3b8;margin:0 0 24px;font-size:14px;">Use the code below to reset your password. It expires in <strong style="color:#f59e0b;">10 minutes</strong>.</p>
          <div style="background:#0f172a;border:2px solid #f59e0b;border-radius:12px;padding:24px;text-align:center;margin-bottom:24px;">
            <div style="font-size:42px;font-weight:800;letter-spacing:12px;color:#fbbf24;font-family:monospace;">{otp_code}</div>
          </div>
          <div style="background:#1a2744;border-left:4px solid #ef4444;border-radius:4px;padding:12px 16px;">
            <p style="color:#fca5a5;font-size:12px;margin:0;">⚠️ If you did not request this, your account is safe — ignore this email.</p>
          </div>
        </div>
        <div style="background:#0f172a;padding:20px;text-align:center;border-top:1px solid #334155;">
          <p style="color:#475569;font-size:11px;margin:0;">© 2025 EduAI Smart Analytics Platform</p>
        </div>
      </div></body></html>"""
    mail.send(msg)


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    from database.models import User, OTPCode
    db, bcrypt, mail = _get_extensions()

    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user  = User.query.filter_by(email=email).first()
        if user:
            OTPCode.query.filter_by(user_id=user.id, used=False).update({'used': True})
            db.session.commit()
            otp_code  = generate_otp()
            expires   = datetime.utcnow() + timedelta(minutes=10)
            otp_entry = OTPCode(user_id=user.id, code=otp_code, expires_at=expires)
            db.session.add(otp_entry)
            db.session.commit()
            try:
                send_reset_email(mail, email, user.name, otp_code)
            except Exception as e:
                flash(f'Failed to send reset email: {str(e)}', 'danger')
                return render_template('auth/forgot_password.html')
        session['reset_email'] = email
        flash(f'If an account exists for {email}, a reset code has been sent. Check your inbox.', 'success')
        return redirect(url_for('auth.reset_password'))

    return render_template('auth/forgot_password.html')


# ─────────────────────────────────────────────────────────────────────────────
# RESET PASSWORD — step 2: verify OTP + set new password
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    from database.models import User, OTPCode
    db, bcrypt, mail = _get_extensions()

    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    email = session.get('reset_email')
    if not email:
        flash('Session expired. Please start again.', 'warning')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        action = request.form.get('action', 'reset')

        if action == 'resend':
            user = User.query.filter_by(email=email).first()
            if user:
                OTPCode.query.filter_by(user_id=user.id, used=False).update({'used': True})
                db.session.commit()
                otp_code  = generate_otp()
                expires   = datetime.utcnow() + timedelta(minutes=10)
                otp_entry = OTPCode(user_id=user.id, code=otp_code, expires_at=expires)
                db.session.add(otp_entry)
                db.session.commit()
                try:
                    send_reset_email(mail, email, user.name, otp_code)
                    flash('New reset code sent!', 'success')
                except Exception as e:
                    flash(f'Failed to resend: {str(e)}', 'danger')
            return redirect(url_for('auth.reset_password'))

        entered      = request.form.get('otp', '').strip()
        new_password = request.form.get('new_password', '')
        confirm      = request.form.get('confirm_password', '')

        if not entered or len(entered) != 6:
            flash('Please enter the 6-digit reset code.', 'warning')
            return render_template('auth/reset_password.html', email=email)
        if len(new_password) < 8:
            flash('New password must be at least 8 characters.', 'warning')
            return render_template('auth/reset_password.html', email=email)
        if new_password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', email=email)

        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Account not found.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        latest_otp = OTPCode.query.filter_by(user_id=user.id, used=False)\
                                   .order_by(OTPCode.created_at.desc()).first()
        if not latest_otp or not latest_otp.is_valid():
            flash('Code has expired. Please request a new one.', 'danger')
            return render_template('auth/reset_password.html', email=email)
        if latest_otp.code != entered:
            flash('Incorrect code. Please try again.', 'danger')
            return render_template('auth/reset_password.html', email=email)

        latest_otp.used    = True
        user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        user.is_verified   = True
        db.session.commit()
        session.pop('reset_email', None)
        flash('Password reset successfully! Please log in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', email=email)

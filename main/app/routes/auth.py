from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import time
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timezone, timedelta

from ..extensions import db, limiter
from ..models import User
from ..utils.security import is_safe_url, validate_password
from ..utils.logging import log_usage

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    error = None
    if request.method == 'POST':
        role = request.form.get('role', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username, role=role).first()

        if user:
            if user.account_locked_until:
                lock_time = user.account_locked_until.replace(tzinfo=timezone.utc) if user.account_locked_until.tzinfo is None else user.account_locked_until
                now_time = datetime.now(timezone.utc)
                if lock_time > now_time:
                    remaining = int((lock_time - now_time).total_seconds() / 60)
                    flash(f'Account locked. Try again in {remaining} minutes.')
                    return redirect(url_for('auth.login'))

        password_valid = False
        if user:
            password_valid = user.check_password(password)
        else:
            dummy_hash = generate_password_hash('dummy_password')
            check_password_hash(dummy_hash, password)
            password_valid = False

        if user and password_valid:
            user.failed_login_attempts = 0
            user.account_locked_until = None
            db.session.commit()

            login_user(user)

            session['username'] = username
            session['role'] = role
            log_usage('login')
            
            if getattr(user, 'must_change_password', False):
                return redirect(url_for('auth.change_password'))
            
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            else:
                return redirect(url_for('admin.admin_dashboard')) if role == 'Admin' else redirect(url_for('main.index'))
        else:
            if user:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= 5:
                    user.account_locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                    flash('Account locked for 15 minutes due to multiple failed attempts.')
                else:
                    flash(f'Invalid credentials. {5 - user.failed_login_attempts} attempts remaining.')
                db.session.commit()
            
            time.sleep(0.1 + (hash(username) % 200) / 1000.0)
            error = "Invalid credentials or role"
    return render_template('login.html', error=error)

@auth_bp.route('/logout')
@login_required
def logout():
    log_usage('logout')
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if not getattr(current_user, 'must_change_password', False):
        return redirect(url_for('main.index'))
    
    error = None
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            error = "Passwords do not match."
        else:
            is_valid, msg = validate_password(new_password)
            if not is_valid:
                error = msg
            else:
                current_user.set_password(new_password)
                current_user.must_change_password = False
                db.session.commit()
                flash("Password updated successfully. Please login again.")
                logout_user()
                return redirect(url_for('auth.login'))
                
    return render_template('change_password.html', error=error)

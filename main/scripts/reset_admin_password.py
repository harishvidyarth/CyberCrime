from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    username = 'admin'
    new_password = 'admin123'
    
    user = User.query.filter_by(username=username).first()
    if user:
        print(f"Resetting password for user: {user.username}")
        # Bypass validation to allow 'admin123' if strictly needed, 
        # though strictly speaking we should enforce strong passwords.
        # But for recovery/remediation as requested:
        user.password_hash = generate_password_hash(new_password)
        user.failed_login_attempts = 0
        user.account_locked_until = None
        user.must_change_password = False
        
        db.session.commit()
        print(f"Password reset to '{new_password}' successfully.")
        print("Account unlocked and failed attempts reset.")
    else:
        print(f"User '{username}' not found. Creating user...")
        # Create admin if missing
        user = User(
            username=username,
            role='Admin',
            name='Administrator',
            email='admin@example.com'
        )
        user.password_hash = generate_password_hash(new_password)
        db.session.add(user)
        db.session.commit()
        print(f"User '{username}' created with password '{new_password}'.")

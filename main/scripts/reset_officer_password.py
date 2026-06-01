from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    user = User.query.filter_by(username='officer').first()
    if user:
        print(f"Resetting password for {user.username}...")
        # Bypassing complexity check for manual reset to restore expected access
        user.password_hash = generate_password_hash('officer123')
        user.failed_login_attempts = 0
        user.account_locked_until = None
        user.must_change_password = False # Optional: prevent forced change if it interferes with immediate testing
        db.session.commit()
        print("Password reset to 'officer123' successfully.")
    else:
        print("User 'officer' not found. Creating...")
        user = User(username='officer', role='Investigative Officer')
        user.password_hash = generate_password_hash('officer123')
        db.session.add(user)
        db.session.commit()
        print("User 'officer' created with password 'officer123'.")

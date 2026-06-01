from app import app, db, User
from werkzeug.security import generate_password_hash

def reset_viewer_password():
    with app.app_context():
        user = User.query.filter_by(username='viewer').first()
        if not user:
            print("Viewer user not found! Creating one...")
            user = User(username='viewer', role='Viewer', name='Public Viewer')
            db.session.add(user)
        
        # Bypass validation in models.py (which requires 12+ chars, special chars, etc.)
        # since 'viewer123' does not meet those requirements.
        print("Setting password to 'viewer123'...")
        user.password_hash = generate_password_hash('viewer123')
        
        # Ensure account is unlocked and not forced to change password immediately
        # (since we are manually setting it to a known value for testing)
        user.must_change_password = False 
        user.account_locked_until = None
        user.failed_login_attempts = 0
        
        db.session.commit()
        print("Successfully updated password for user 'viewer' to 'viewer123'.")

if __name__ == "__main__":
    reset_viewer_password()

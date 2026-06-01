from app import app, db, User
from werkzeug.security import check_password_hash

def check_creds():
    with app.app_context():
        user = User.query.filter_by(username='viewer').first()
        if user:
            print(f"User found: {user.username}")
            print(f"Role: {user.role}")
            print(f"Locked until: {user.account_locked_until}")
            print(f"Failed attempts: {user.failed_login_attempts}")
            
            # Check password
            if check_password_hash(user.password_hash, 'viewer123'):
                print("PASS: Password 'viewer123' is CORRECT.")
            else:
                print("FAIL: Password 'viewer123' is INCORRECT.")
        else:
            print("User 'viewer' not found.")

if __name__ == "__main__":
    check_creds()

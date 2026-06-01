
from app import app, db, User
from werkzeug.security import generate_password_hash

ACCOUNTS = [
    ("officer", "Investigative Officer", "officer123"),
    ("admin", "Admin", "admin123"),
    ("viewer", "Viewer", "viewer123"),
]

with app.app_context():
    for username, role, password in ACCOUNTS:
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"User '{username}' found. Current role: {user.role}")
            user.role = role
            user.password_hash = generate_password_hash(password)
            user.failed_login_attempts = 0
            user.account_locked_until = None
            db.session.commit()
            print(f"Password for '{username}' reset to '{password}'. Account unlocked.")
        else:
            print(f"User '{username}' not found. Creating it...")
            user = User(username=username, role=role)
            user.password_hash = generate_password_hash(password)
            db.session.add(user)
            db.session.commit()
            print(f"User '{username}' created with password '{password}'.")


from app import app, db, User
from werkzeug.security import check_password_hash, generate_password_hash

with app.app_context():
    user = User.query.filter_by(username='officer').first()
    if user:
        print(f"User 'officer' found.")
        print(f"Role: {user.role}")
        print(f"Password 'officer123' valid? {check_password_hash(user.password_hash, 'officer123')}")
        print(f"Password 'Officer@123456' valid? {check_password_hash(user.password_hash, 'Officer@123456')}")
    else:
        print("User 'officer' not found.")

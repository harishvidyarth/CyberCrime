from app import app, db, User

with app.app_context():
    user = User.query.filter_by(username='officer').first()
    if user:
        print(f"User found: {user.username}")
        print(f"Role: {user.role}")
        print(f"Failed login attempts: {user.failed_login_attempts}")
        print(f"Account locked until: {user.account_locked_until}")
        # We can't print password_hash directly as it's hashed, but we can verify it
        is_valid = user.check_password('officer123')
        print(f"Password 'officer123' valid: {is_valid}")
        
        # Also check if password matches 'Password123!' which might be the new default
        is_valid_default = user.check_password('Password123!')
        print(f"Password 'Password123!' valid: {is_valid_default}")
    else:
        print("User 'officer' NOT FOUND")

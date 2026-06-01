from app import app, db, User

with app.app_context():
    username = 'admin'
    print(f"Checking status for user: {username}")
    user = User.query.filter_by(username=username).first()
    
    if user:
        print(f"User found: {user.username}")
        print(f"ID: {user.id}")
        print(f"Role: {user.role}")
        print(f"Failed login attempts: {user.failed_login_attempts}")
        print(f"Account locked until: {user.account_locked_until}")
        
        # Verify password 'admin123'
        password_to_check = 'admin123'
        is_valid = user.check_password(password_to_check)
        print(f"Password '{password_to_check}' valid: {is_valid}")
        
        if not is_valid:
            print("Password mismatch. Attempting to verify with other common passwords...")
            common_passwords = ['admin', 'Admin123!', 'password']
            for pwd in common_passwords:
                if user.check_password(pwd):
                    print(f"Match found with: {pwd}")
                    break
    else:
        print(f"User '{username}' NOT FOUND")


from app import app, db, User
import secrets
import string

def generate_secure_password(length=16):
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*(),.?":{}|<>'
    while True:
        password = ''.join(secrets.choice(alphabet) for i in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in '!@#$%^&*(),.?":{}|<>' for c in password)):
            return password

with app.app_context():
    try:
        # Check model field
        print(f"Checking User model field 'must_change_password'...")
        u = User(username='test_verify_2', role='Viewer')
        if hasattr(u, 'must_change_password'):
            print("Field 'must_change_password' exists on User model.")
        else:
            print("ERROR: Field 'must_change_password' MISSING on User model.")
            
        # Simulate the remediation logic
        print("Simulating remediation logic with secure password...")
        pwd = generate_secure_password()
        print(f"Generated password: {pwd}")
        
        u.set_password(pwd)
        u.must_change_password = True
        db.session.add(u)
        db.session.commit()
        
        # Verify persistence
        u_db = User.query.filter_by(username='test_verify_2').first()
        print(f"Persisted 'must_change_password' value: {u_db.must_change_password}")
        
        # Clean up
        db.session.delete(u_db)
        db.session.commit()
        print("Verification successful.")
        
    except Exception as e:
        print(f"Verification FAILED: {e}")

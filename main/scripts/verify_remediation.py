
from app import app, db, User
import secrets

with app.app_context():
    try:
        # Check model field
        print(f"Checking User model field 'must_change_password'...")
        u = User(username='test_verify', role='Viewer')
        if hasattr(u, 'must_change_password'):
            print("Field 'must_change_password' exists on User model.")
            print(f"Default value: {u.must_change_password}")
        else:
            print("ERROR: Field 'must_change_password' MISSING on User model.")
            
        # Simulate the remediation logic
        print("Simulating remediation logic...")
        pwd = secrets.token_urlsafe(16)
        u.set_password(pwd)
        u.must_change_password = True
        db.session.add(u)
        db.session.commit()
        
        # Verify persistence
        u_db = User.query.filter_by(username='test_verify').first()
        print(f"Persisted value: {u_db.must_change_password}")
        
        # Clean up
        db.session.delete(u_db)
        db.session.commit()
        print("Verification successful.")
        
    except Exception as e:
        print(f"Verification FAILED: {e}")

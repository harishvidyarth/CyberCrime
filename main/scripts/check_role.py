
from app import app, db, User

with app.app_context():
    username = 'officer'
    role = 'Investigative Officer'
    user = User.query.filter_by(username=username, role=role).first()
    if user:
        print(f"User found with username='{username}' and role='{role}'")
    else:
        print(f"User NOT found with username='{username}' and role='{role}'")
        
    # Check what is in DB
    u = User.query.filter_by(username=username).first()
    if u:
        print(f"Actual role in DB: '{u.role}'")
        print(f"Repr of role: {repr(u.role)}")

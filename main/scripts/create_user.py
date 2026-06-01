from app import app
from models import db, User

with app.app_context():
    db.create_all()
    
    # Check if users already exist to avoid duplicates or primary key errors
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='Admin')
        admin.set_password('Admin@123456')
        db.session.add(admin)
        print("Admin user created.")

    if not User.query.filter_by(username='officer').first():
        officer = User(username='officer', role='Investigative Officer')
        officer.set_password('Officer@123456')
        db.session.add(officer)
        print("Officer user created.")

    if not User.query.filter_by(username='viewer').first():
        viewer = User(username='viewer', role='Viewer')
        viewer.set_password('Viewer@123456')
        db.session.add(viewer)
        print("Viewer user created.")

    db.session.commit()
    print("User initialization complete.")

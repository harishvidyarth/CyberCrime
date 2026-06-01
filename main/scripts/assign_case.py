from app import app, db, User, Complaint

ack_no = '22903250021752'
username = 'officer'

with app.app_context():
    user = User.query.filter_by(username=username).first()
    if not user:
        print(f"User '{username}' not found!")
        exit(1)

    complaint = Complaint.query.filter_by(ack_no=ack_no).first()
    if not complaint:
        print(f"Complaint '{ack_no}' not found!")
        # Try finding ANY complaint to assign, to be helpful
        complaint = Complaint.query.first()
        if complaint:
            print(f"Assigning alternative complaint '{complaint.ack_no}' instead.")
        else:
            print("No complaints found in database.")
            exit(1)
    
    print(f"Assigning complaint {complaint.ack_no} to user {user.username} (ID: {user.id})...")
    complaint.assigned_to = user.id
    db.session.commit()
    print("Assignment successful.")

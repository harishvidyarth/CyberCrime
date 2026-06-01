from app import app, db, User, Complaint
from flask import Flask

# Mocking current_user for the script
class MockUser:
    def __init__(self, id, role):
        self.id = id
        self.role = role

with app.app_context():
    username = 'officer'
    ack_no = '22903250021752'
    
    user = User.query.filter_by(username=username).first()
    if not user:
        print(f"User {username} not found")
        exit(1)
        
    complaint = Complaint.query.filter_by(ack_no=ack_no).first()
    if not complaint:
        print(f"Complaint {ack_no} not found")
        exit(1)
        
    print(f"Checking access for User: {user.username} (ID: {user.id}, Role: {user.role})")
    print(f"Complaint: {complaint.ack_no} (Uploaded By: {complaint.uploaded_by}, Assigned To: {complaint.assigned_to})")
    
    if user.role == 'Admin':
        print("Access GRANTED (Admin)")
    elif complaint.assigned_to == user.id or complaint.uploaded_by == user.id:
        print("Access GRANTED (Owner/Assignee)")
    else:
        print("Access DENIED")

from app import app, db, Complaint, Transaction, User

with app.app_context():
    # Find officer user
    officer = User.query.filter_by(username='officer').first()
    if not officer:
        print("User 'officer' not found. Creating...")
        officer = User(username='officer', role='Investigative Officer')
        officer.set_password('officer123')
        db.session.add(officer)
        db.session.commit()
    
    print(f"Assigning orphaned cases to: {officer.username}")

    # Get all unique ACK numbers from Transactions
    ack_nos = db.session.query(Transaction.ack_no).distinct().all()
    ack_nos = [a[0] for a in ack_nos if a[0]]
    
    print(f"Found {len(ack_nos)} unique ACK numbers in Transactions.")
    
    count = 0
    for ack in ack_nos:
        exists = Complaint.query.filter_by(ack_no=ack).first()
        if not exists:
            print(f"Creating Complaint record for orphaned ACK: {ack}")
            # Try to infer upload time from first transaction or now
            complaint = Complaint(
                ack_no=ack,
                file_name=f"Legacy_Case_{ack}",
                uploaded_by=officer.id,  # Assign ownership to officer so they can view it
                assigned_to=officer.id,
                upload_time=db.func.now()
            )
            db.session.add(complaint)
            count += 1
            
    if count > 0:
        db.session.commit()
        print(f"Successfully backfilled {count} Complaint records.")
    else:
        print("No orphaned cases found.")

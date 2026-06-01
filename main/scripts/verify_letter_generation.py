from app import app, db, Transaction
import json
import os
from datetime import datetime

def verify_generation():
    import os
    if os.environ.get('FLASK_ENV') == 'testing':
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
    else:
        app.config['TESTING'] = False
        app.config['WTF_CSRF_ENABLED'] = True
    
    # Ensure we have a dummy transaction with a layer and date
    with app.app_context():
        # Clean up old test data
        Transaction.query.filter_by(ack_no="TEST_LETTER_GEN").delete()
        
        t = Transaction(
            ack_no="TEST_LETTER_GEN",
            account_number="ACC123",
            to_account="ACC123", # For suspect match
            amount=50000.0,
            txn_date="15-01-2024", # DD-MM-YYYY
            layer="2",
            bank_name="Test Bank",
            txn_id="TXN100",
            ifsc_code="TEST0001",
            put_on_hold_txn_id="POH123", # For POH
            put_on_hold_amount=50000.0,
            put_on_hold_date="15-01-2024"
        )
        db.session.add(t)
        db.session.commit()
        
        print("Created test transaction.")

    client = app.test_client()
    
    payload = {
        "ack_no": "TEST_LETTER_GEN",
        "account_number": "ACC123",
        "letter_type": "suspect",
        "is_poh": True,
        "officer_name": "Officer Test",
        "ncrp_ack_no": "TEST_LETTER_GEN"
    }
    
    print("Sending request...")
    res = client.post('/generate_letter_docx', json=payload, follow_redirects=True)
    
    if res.status_code == 200:
        print("Success: Letter generated.")
        # We can't easily verify the DOCX content for replacements without the specific template,
        # but a 200 OK means the code ran through the new logic without crashing.
    else:
        print(f"Failed: {res.status_code}")
        print(res.text)

if __name__ == "__main__":
    verify_generation()


from app import app, db, Transaction
from sqlalchemy import or_

with app.app_context():
    account = '925020036850040'
    print(f"Searching for account: {account}")
    
    # Try to find the transaction
    txns = Transaction.query.filter(
        or_(Transaction.account_number == account, Transaction.to_account == account)
    ).all()
    
    print(f"Found {len(txns)} transactions.")
    if txns:
        t = txns[0]
        print(f"Sample txn: ack_no={t.ack_no}, poh_id={t.put_on_hold_txn_id}, poh_amt={t.put_on_hold_amount}")
        
        # Test the generation logic locally
        import requests
        url = "http://127.0.0.1:5000/generate_letter_docx"
        payload = {
            "ack_no": t.ack_no,
            "account_number": account,
            "letter_type": "suspect",
            "is_poh": True,
            "officer_name": "Test Officer",
            "officer_designation": "Inspector",
            "officer_phone": "1234567890",
            "officer_email": "test@police.gov.in",
            "letter_date": "22-01-2025",
            "crime_no": "123/2025",
            "ncrp_ack_no": t.ack_no
        }
        
        print("Sending POST request to localhost...")
        try:
            res = requests.post(url, json=payload, timeout=(3.05, 27))
            print(f"Status Code: {res.status_code}")
            print(f"Response Text: {res.text[:200]}")
        except Exception as e:
            print(f"Request failed: {e}")
    else:
        print("No transactions found for this account.")

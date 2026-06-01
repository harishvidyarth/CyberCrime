from app import app, db, Transaction, KYCDetails
import json

def test_kyc_persistence():
    import os
    if os.environ.get('FLASK_ENV') == 'testing':
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
    else:
        app.config['TESTING'] = False
        app.config['WTF_CSRF_ENABLED'] = True
    with app.app_context():
        # Setup test data
        ack_no = "TEST_ACK_KYC_001"
        txn_id = "TEST_TXN_KYC_001"
        
        # Cleanup
        db.session.query(Transaction).filter_by(ack_no=ack_no).delete()
        KYCDetails.query.filter_by(txn_id=txn_id).delete()
        db.session.commit()

        # Create dummy transaction
        txn = Transaction(
            ack_no=ack_no,
            txn_id=txn_id,
            to_account="9999999999",
            amount=1000.0,
            txn_date="01-01-2025"
        )
        db.session.add(txn)
        db.session.commit()
        print("Test transaction created.")

        # Test save_kyc via client
        client = app.test_client()
        
        print("Calling /save_kyc...")
        payload = {
            "txn_id": txn_id,
            "name": "John Doe",
            "aadhar": "1234-5678-9012",
            "mobile": "9876543210",
            "address": "123 Baker Street"
        }
        res = client.post('/save_kyc', json=payload)
        print(f"Save Status: {res.status_code}, Response: {res.json}")
        assert res.status_code == 200
        assert res.json['status'] == 'success'

        # Verify persistent storage
        kyc_entry = KYCDetails.query.filter_by(txn_id=txn_id).first()
        print(f"Persistent Entry: {kyc_entry.name}, {kyc_entry.address}")
        assert kyc_entry is not None
        assert kyc_entry.name == "John Doe"
        assert kyc_entry.address == "123 Baker Street"
        print("SUCCESS: Data saved to KYCDetails table.")

        # Test graph_data route retrieval
        print("Calling /graph_data/...")
        res = client.get(f'/graph_data/{ack_no}')
        data = res.json
        
        # Helper to find node
        def find_node(node):
            if node.get('txid') == txn_id:
                return node
            if 'children' in node:
                for child in node['children']:
                    found = find_node(child)
                    if found: return found
            return None

        node = find_node(data)
        if node:
            print(f"Found node KYC: Name={node.get('kyc_name')}, Address={node.get('kyc_address')}")
            assert node.get('kyc_name') == "John Doe"
            assert node.get('kyc_address') == "123 Baker Street"
            print("SUCCESS: graph_data returned persistent KYC details.")
        else:
            print("FAILURE: Could not find node in graph response.")

        # Cleanup
        db.session.query(Transaction).filter_by(ack_no=ack_no).delete()
        KYCDetails.query.filter_by(txn_id=txn_id).delete()
        db.session.commit()
        print("\nTest completed successfully.")

if __name__ == "__main__":
    test_kyc_persistence()

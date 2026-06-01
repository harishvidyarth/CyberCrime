from app import app, db, Transaction, POHRefundDetails
import json

def test_poh_api_integration():
    with app.app_context():
        # Setup test data
        ack_no = "TEST_ACK_API_001"
        txn_id = "TEST_TXN_API_001"
        acc_no = "1234567890"

        # Cleanup
        db.session.query(Transaction).filter_by(ack_no=ack_no).delete()
        POHRefundDetails.query.filter_by(ack_no=ack_no).delete()
        db.session.commit()

        # Create dummy transaction
        txn = Transaction(
            ack_no=ack_no,
            put_on_hold_txn_id=txn_id,
            to_account=acc_no,
            amount=1000.0,
            txn_date="01-01-2025",
            # Intentionally leave refund details empty in Transaction table
            court_order_date=None,
            refund_status=None,
            refund_amount=None
        )
        db.session.add(txn)
        
        # Create persistent POH detail
        poh = POHRefundDetails(
            ack_no=ack_no,
            txn_id=txn_id,
            court_order_date="2025-01-01",
            refund_status="Refunded",
            refund_amount=1000.0
        )
        db.session.add(poh)
        db.session.commit()

        print("Test data created.")

        # Test graph_data route logic
        # We can call the route function directly or use test_client
        client = app.test_client()
        
        print("Calling /graph_data/...")
        res = client.get(f'/graph_data/{ack_no}')
        if res.status_code != 200:
            print(f"Error calling graph_data: {res.status_code} {res.data}")
            return

        data = res.json
        # The response structure is complex (D3 hierarchy)
        # We need to find the node with our transaction
        # Root -> children -> ...
        
        # Helper to find node
        def find_poh_info(node):
            if node.get('hold_info') and node['hold_info'].get('txn_id') == txn_id:
                return node['hold_info']
            if 'children' in node:
                for child in node['children']:
                    found = find_poh_info(child)
                    if found: return found
            return None

        hold_info = find_poh_info(data)
        if hold_info:
            print(f"Found hold_info: {hold_info}")
            assert hold_info['court_order_date'] == "2025-01-01"
            assert hold_info['refund_status'] == "Refunded"
            assert hold_info['refund_amount'] == 1000.0
            print("SUCCESS: graph_data returned persistent details correctly.")
        else:
            print("FAILURE: Could not find hold_info in graph response.")
            print(json.dumps(data, indent=2))

        # Test put_on_hold_transactions route logic
        print("\nCalling /put_on_hold_transactions/...")
        res = client.get(f'/put_on_hold_transactions/{ack_no}')
        data = res.json
        if data and isinstance(data, list) and len(data) > 0:
            item = data[0]
            print(f"Item: {item}")
            assert item['court_order_date'] == "2025-01-01"
            assert item['refund_status'] == "Refunded"
            assert item['refund_amount'] == 1000.0
            print("SUCCESS: put_on_hold_transactions returned persistent details correctly.")
        else:
             print("FAILURE: No data returned from put_on_hold_transactions.")

        # Cleanup
        db.session.query(Transaction).filter_by(ack_no=ack_no).delete()
        POHRefundDetails.query.filter_by(ack_no=ack_no).delete()
        db.session.commit()
        print("\nTest completed.")

if __name__ == "__main__":
    test_poh_api_integration()

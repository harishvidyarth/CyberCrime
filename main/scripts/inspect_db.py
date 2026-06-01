from app import app, db
from models import Complaint, Transaction
from sqlalchemy import inspect

with app.app_context():
    # Check default bind
    print("--- Default Bind (fundtrail.db) ---")
    try:
        txn_count = db.session.query(Transaction).count()
        print(f"Transaction count: {txn_count}")
    except Exception as e:
        print(f"Error counting transactions: {e}")
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"Tables: {tables}")
    
    # Check POH bind
    print("\n--- POH Bind (poh_store) ---")
    try:
        poh_engine = db.get_engine(app, bind='poh_store')
        poh_inspector = inspect(poh_engine)
        poh_tables = poh_inspector.get_table_names()
        print(f"Tables: {poh_tables}")
        if 'poh_refund_details' in poh_tables:
            cols = [c['name'] for c in poh_inspector.get_columns('poh_refund_details')]
            print(f"Columns in poh_refund_details: {cols}")
    except Exception as e:
        print(f"Error checking POH bind: {e}")

    # List some complaints
    try:
        complaints = db.session.query(Complaint).limit(5).all()
        print(f"Complaints: {[c.ack_no for c in complaints]}")
    except Exception as e:
        print(f"Error querying complaints: {e}")

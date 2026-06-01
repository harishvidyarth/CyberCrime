from app import app, db
from sqlalchemy import text

with app.app_context():
    with db.engine.connect() as conn:
        print("Attempting to create indexes...")
        
        # Index for ack_no
        try:
            # MySQL syntax for creating index if not exists is not standard in older versions, 
            # so we just try to create and catch exception if it exists.
            conn.execute(text("CREATE INDEX idx_transaction_ack_no ON transaction (ack_no)"))
            print("Successfully created index 'idx_transaction_ack_no'")
        except Exception as e:
            print(f"Index 'idx_transaction_ack_no' creation skipped (may already exist): {e}")

        # Index for put_on_hold_txn_id
        try:
            conn.execute(text("CREATE INDEX idx_transaction_put_on_hold ON transaction (put_on_hold_txn_id)"))
            print("Successfully created index 'idx_transaction_put_on_hold'")
        except Exception as e:
            print(f"Index 'idx_transaction_put_on_hold' creation skipped (may already exist): {e}")

        # Index for upload_id
        try:
            conn.execute(text("CREATE INDEX idx_transaction_upload_id ON transaction (upload_id)"))
            print("Successfully created index 'idx_transaction_upload_id'")
        except Exception as e:
            print(f"Index 'idx_transaction_upload_id' creation skipped (may already exist): {e}")
            
    print("Index creation process finished.")

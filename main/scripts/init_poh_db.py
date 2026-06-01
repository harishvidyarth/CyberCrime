from app import app, db
import os

with app.app_context():
    print("Creating tables for all binds...")
    db.create_all()
    
    engine = db.get_engine(bind='poh_store')
    poh_db_path = engine.url.database
    print(f"Checking for file at: {poh_db_path}")
    
    if os.path.exists(poh_db_path):
        print(f"SUCCESS: Database file created at {poh_db_path}")
    else:
        print("ERROR: Database file NOT found in project root.")

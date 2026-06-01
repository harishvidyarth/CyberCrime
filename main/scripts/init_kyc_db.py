from app import app, db, KYCDetails
import os

with app.app_context():
    print("Re-creating tables for KYC bind...")
    engine = db.get_engine(bind='kyc_store')
    KYCDetails.__table__.drop(engine, checkfirst=True)
    KYCDetails.__table__.create(engine)
    
    kyc_db_path = engine.url.database
    print(f"Checking for file at: {kyc_db_path}")
    
    if os.path.exists(kyc_db_path):
        print(f"SUCCESS: KYC Database file created at {kyc_db_path}")
    else:
        print("ERROR: KYC Database file NOT found in project root.")

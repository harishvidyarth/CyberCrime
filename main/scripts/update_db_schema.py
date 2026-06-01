
from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE user ADD COLUMN must_change_password BOOLEAN DEFAULT 0"))
            conn.commit()
        print("Column 'must_change_password' added successfully.")
    except Exception as e:
        print(f"Error adding column: {e}")

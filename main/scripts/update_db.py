import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.join(os.getcwd(), 'working file repeatcr(15-10)/fundtrail_backend_web_ (2)_updated/fundtrail_backend_web_/fundtrail_backend_web_/fundtrail_backend_web'))

from models import db, Transaction
from flask import Flask

app = Flask(__name__)
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'fundtrail_db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def get_state(ifsc):
    try:
        from ifsc_utils import get_state as excel_get_state
        return excel_get_state(ifsc)
    except Exception:
        return 'Unknown'

with app.app_context():
    db.create_all()
    print('Database updated')

    # Update state for transactions where state is None
    transactions = Transaction.query.filter(Transaction.state.is_(None)).all()
    print(f'Found {len(transactions)} transactions with missing state')
    for t in transactions:
        if t.ifsc_code:
            state = get_state(t.ifsc_code)
            t.state = state
            print(f'Updated {t.ifsc_code} to state {state}')
    db.session.commit()
    print('States updated')

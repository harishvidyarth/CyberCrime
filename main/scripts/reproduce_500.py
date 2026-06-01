
import unittest
from app import app, db, User, Complaint, Transaction
from flask_login import login_user

class Test500(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.app = app
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        
        # Create a test user
        self.user = User.query.filter_by(username='test_user_500').first()
        if not self.user:
            self.user = User(username='test_user_500', role='Investigative Officer')
            self.user.set_password('Password123!')
            db.session.add(self.user)
            db.session.commit()

    def tearDown(self):
        self.app_context.pop()

    def login(self):
        return self.client.post('/login', data=dict(
            username='test_user_500',
            password='Password123!',
            role='Investigative Officer'
        ), follow_redirects=True)

    def test_atm_data_existing_ack(self):
        self.login()
        # Create a dummy transaction
        ack_no = 'TEST_ACK_500'
        # Ensure cleanup
        Transaction.query.filter_by(ack_no=ack_no).delete()
        Complaint.query.filter_by(ack_no=ack_no).delete()
        db.session.commit()

        # Create Complaint
        complaint = Complaint(ack_no=ack_no, assigned_to=self.user.id, file_name='test.xlsx', upload_time=db.func.now())
        db.session.add(complaint)
        
        # Create Transaction
        txn = Transaction(ack_no=ack_no, amount=100.0, txn_id='TXN123', from_account='ACC1', to_account='ACC2')
        db.session.add(txn)
        db.session.commit()

        print(f"\nTesting /atm_data/{ack_no}...")
        resp = self.client.get(f'/atm_data/{ack_no}')
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 500:
             print(f"Response: {resp.get_json()}")
        self.assertNotEqual(resp.status_code, 500)

        # Cleanup
        Transaction.query.filter_by(ack_no=ack_no).delete()
        Complaint.query.filter_by(ack_no=ack_no).delete()
        db.session.commit()

if __name__ == '__main__':
    unittest.main()

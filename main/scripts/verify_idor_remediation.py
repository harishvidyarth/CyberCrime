
import unittest
from app import app, db, User, Complaint, Transaction
from flask_login import login_user
import json

class TestIDORRemediation(unittest.TestCase):
    def setUp(self):
        # Force config change
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        self.app = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()
        
        # Ensure we are disconnected from any previous DB
        db.session.remove()
        db.engine.dispose()
        
        # Verify we are using memory DB
        # Note: db.engine might recreate based on config now
        if 'memory' not in str(db.engine.url):
             # Try to force it?
             pass
        
        # Create tables in the (hopefully) new memory DB
        db.create_all()

        # Check if users exist (if we failed to switch DB, this prevents crash but warns)
        if User.query.filter_by(username='admin_test').first():
             # We are likely in a dirty DB, let's clean up our test users only
             User.query.filter_by(username='admin_test').delete()
             User.query.filter_by(username='officer_test').delete()
             User.query.filter_by(username='viewer_test').delete()
             db.session.commit()

        # Create Users with TEST suffixes to avoid prod collision
        self.admin = User(username='admin_test', role='Admin')
        self.admin.set_password('AdminPassword123!')
        
        self.officer = User(username='officer_test', role='Investigative Officer')
        self.officer.set_password('OfficerPassword123!')
        
        self.viewer = User(username='viewer_test', role='Viewer')
        self.viewer.set_password('ViewerPassword123!')

        db.session.add_all([self.admin, self.officer, self.viewer])
        db.session.commit()

        # Clean up existing test complaints and transactions if they persist
        test_acks = ["ACK-OFFICER-1", "ACK-ADMIN-ONLY"]
        try:
            Transaction.query.filter(Transaction.ack_no.in_(test_acks)).delete(synchronize_session=False)
            Complaint.query.filter(Complaint.ack_no.in_(test_acks)).delete(synchronize_session=False)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Cleanup warning: {e}")

        # Create Data
        # Case 1: Assigned to Officer
        self.case1_ack = "ACK-OFFICER-1"
        self.complaint1 = Complaint(ack_no=self.case1_ack, assigned_to=self.officer.id)
        self.txn1 = Transaction(ack_no=self.case1_ack, amount=100.0, layer=1)
        
        # Case 2: Unassigned (Admin only)
        self.case2_ack = "ACK-ADMIN-ONLY"
        self.complaint2 = Complaint(ack_no=self.case2_ack) # Not assigned
        self.txn2 = Transaction(ack_no=self.case2_ack, amount=200.0, layer=1)

        db.session.add_all([self.complaint1, self.txn1, self.complaint2, self.txn2])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        # Only drop if we are sure it's memory
        if 'memory' in str(db.engine.url):
            db.drop_all()
        self.ctx.pop()

    def login(self, username, password):
        # Map simple names to test names
        user_map = {
            'admin': 'admin_test',
            'officer': 'officer_test',
            'viewer': 'viewer_test'
        }
        real_username = user_map.get(username, username)
        return self.app.post('/login', data=dict(
            username=real_username,
            password=password,
            role=User.query.filter_by(username=real_username).first().role
        ), follow_redirects=True)

    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access sensitive endpoints"""
        endpoints = [
            f'/graph_data/{self.case1_ack}',
            f'/put_on_hold_transactions/{self.case1_ack}',
            f'/statewise_summary/{self.case1_ack}',
            f'/state_transactions/{self.case1_ack}/Delhi',
            f'/atm_data/{self.case1_ack}',
            '/available_ack_nos'
        ]
        
        for endpoint in endpoints:
            response = self.app.get(endpoint)
            # Should redirect to login (302) or return 401/403 depending on config
            # Flask-Login usually redirects to login_view
            self.assertEqual(response.status_code, 302, f"Endpoint {endpoint} accessible without auth!")
            self.assertIn('/login', response.location, f"Endpoint {endpoint} did not redirect to login")

    def test_admin_access(self):
        """Test that Admin can access everything"""
        self.login('admin', 'AdminPassword123!')
        
        # Access Officer's case
        resp = self.app.get(f'/graph_data/{self.case1_ack}')
        self.assertEqual(resp.status_code, 200, "Admin failed to access officer case")
        
        # Access Unassigned case
        resp = self.app.get(f'/graph_data/{self.case2_ack}')
        self.assertEqual(resp.status_code, 200, "Admin failed to access unassigned case")

        # Check available_ack_nos
        resp = self.app.get('/available_ack_nos')
        data = json.loads(resp.data)
        self.assertIn(self.case1_ack, data['available_ack_nos'])
        self.assertIn(self.case2_ack, data['available_ack_nos'])

    def test_officer_access(self):
        """Test IDOR: Officer should only access assigned cases"""
        self.login('officer', 'OfficerPassword123!')
        
        # Access Assigned case -> OK
        resp = self.app.get(f'/graph_data/{self.case1_ack}')
        self.assertEqual(resp.status_code, 200, "Officer failed to access assigned case")
        
        # Access Unassigned case -> FORBIDDEN (IDOR Protected)
        resp = self.app.get(f'/graph_data/{self.case2_ack}')
        self.assertEqual(resp.status_code, 403, "Officer WAS ABLE to access unassigned case (IDOR Vulnerability!)")

        # Check available_ack_nos -> Should only see assigned
        resp = self.app.get('/available_ack_nos')
        data = json.loads(resp.data)
        self.assertIn(self.case1_ack, data['available_ack_nos'])
        self.assertNotIn(self.case2_ack, data['available_ack_nos'], "Officer saw unassigned case in list")

    def test_viewer_access(self):
        """Test Viewer can view all but (implicitly) logic handled"""
        self.login('viewer', 'ViewerPassword123!')
        
        # Access Officer's case
        resp = self.app.get(f'/graph_data/{self.case1_ack}')
        self.assertEqual(resp.status_code, 200)
        
        # Access Unassigned case
        resp = self.app.get(f'/graph_data/{self.case2_ack}')
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()

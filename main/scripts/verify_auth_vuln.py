
from app import app
import unittest

class TestAuthRemediation(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_unauthenticated_access(self):
        print("\nTesting Unauthenticated Access...")
        
        # Test view_analytics
        print("1. Testing /view_analytics...")
        resp = self.client.get('/view_analytics', follow_redirects=True)
        if b'Login' in resp.data:
            print("PASS: /view_analytics redirected to login.")
        elif b'Dashboard' in resp.data or b'Analytics' in resp.data:
             print("FAIL: /view_analytics accessible without login!")
        else:
             print(f"INFO: /view_analytics returned {resp.status_code}")

        # Test admin/add_officer
        print("2. Testing /admin/add_officer...")
        resp = self.client.get('/admin/add_officer', follow_redirects=True)
        if b'Login' in resp.data:
            print("PASS: /admin/add_officer redirected to login.")
        elif b'Add Verification Officer' in resp.data:
             print("FAIL: /admin/add_officer accessible without login!")
        else:
             print(f"INFO: /admin/add_officer returned {resp.status_code}")
             
        # Test graph_data
        print("3. Testing /graph_data/TEST_ACK...")
        resp = self.client.get('/graph_data/TEST_ACK', follow_redirects=True)
        if b'Login' in resp.data:
            print("PASS: /graph_data redirected to login.")
        elif b'error' in resp.data or resp.status_code == 200:
             # It might return JSON error "No transactions found" but that means it EXECUTED the function
             if b'No transactions found' in resp.data:
                 print("FAIL: /graph_data executed logic without login!")
             else:
                 print(f"FAIL: /graph_data accessible without login (Status: {resp.status_code})")
        else:
             print(f"INFO: /graph_data returned {resp.status_code}")

if __name__ == '__main__':
    unittest.main()

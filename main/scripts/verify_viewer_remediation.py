
from app import app
import unittest

class TestViewerRemediation(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_viewer_bypass_prevention(self):
        print("\nTesting Viewer Login Remediation...")
        
        # Attempt login with Viewer role and NO credentials
        response = self.client.post('/login', data={
            'role': 'Viewer',
            'username': '',
            'password': ''
        }, follow_redirects=True)
        
        # Should stay on login page or show error
        # If vulnerable, it would redirect to index
        if b'Dashboard' in response.data:
            print("FAIL: Logged into Dashboard without credentials!")
            self.fail("Vulnerability present: Auto-login allowed.")
        else:
            print("PASS: Access denied without credentials.")
            
        # Attempt login with Viewer role and WRONG credentials
        response = self.client.post('/login', data={
            'role': 'Viewer',
            'username': 'viewer',
            'password': 'WrongPassword123'
        }, follow_redirects=True)
        
        if b'Invalid credentials' in response.data:
             print("PASS: 'Invalid credentials' message displayed for wrong password.")
        else:
             # It might just reload page without flash if validation fails differently, 
             # but we expect "Invalid credentials" from app.py logic
             print("INFO: Response did not contain 'Invalid credentials', checking if still on login page...")
             if b'Login As' in response.data:
                 print("PASS: Still on login page.")
             else:
                 self.fail("Unexpected state: " + str(response.status_code))

if __name__ == '__main__':
    unittest.main()

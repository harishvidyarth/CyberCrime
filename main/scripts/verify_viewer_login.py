
import requests
import sys

# Configuration
BASE_URL = "http://127.0.0.1:5000"
LOGIN_URL = f"{BASE_URL}/login"
DASHBOARD_URL = f"{BASE_URL}/index"

def get_csrf_token(session):
    try:
        response = session.get(LOGIN_URL)
        if response.status_code != 200:
            print(f"[-] Failed to load login page. Status: {response.status_code}")
            return None
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrf_token'})
        if csrf_token:
            return csrf_token['value']
        else:
            print("[-] CSRF token not found")
            return None
    except Exception as e:
        print(f"[-] Error getting CSRF token: {e}")
        return None

def verify_viewer_login():
    print("[*] Verifying Viewer Login with 'viewer123'...")
    session = requests.Session()
    
    csrf_token = get_csrf_token(session)
    if not csrf_token:
        return False

    payload = {
        'csrf_token': csrf_token,
        'role': 'Viewer',
        'username': 'viewer',
        'password': 'viewer123'
    }
    
    try:
        response = session.post(LOGIN_URL, data=payload, allow_redirects=True)
        
        # Check for success indicators
        if response.url.endswith('/index') or 'Welcome' in response.text or 'Dashboard' in response.text:
            print("[+] Login SUCCESSFUL!")
            return True
        elif 'change_password' in response.url:
             print("[!] Redirected to Change Password page (Unexpected but valid login)")
             return True
        else:
            print(f"[-] Login FAILED. URL: {response.url}")
            if 'Invalid credentials' in response.text:
                print("[-] Message: Invalid credentials")
            return False
            
    except Exception as e:
        print(f"[-] Error during login: {e}")
        return False

if __name__ == "__main__":
    if verify_viewer_login():
        sys.exit(0)
    else:
        sys.exit(1)


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
            print("[-] CSRF token not found in login page")
            return None
    except Exception as e:
        print(f"[-] Error getting CSRF token: {e}")
        return None

def test_viewer_bypass():
    print("[*] Testing Viewer Role Authentication Bypass...")
    session = requests.Session()
    
    csrf_token = get_csrf_token(session)
    if not csrf_token:
        print("[-] Aborting due to missing CSRF token")
        return

    # Payload mimicking the attack: Role=Viewer, empty username/password
    payload = {
        'csrf_token': csrf_token,
        'role': 'Viewer',
        'username': '',
        'password': ''
    }
    
    try:
        response = session.post(LOGIN_URL, data=payload, allow_redirects=True)
        
        # Check if we are redirected to index or still on login
        if response.url.endswith('/index') or 'Welcome, Viewer' in response.text:
            print("[!] VULNERABILITY CONFIRMED: Logged in as Viewer without credentials!")
            print(f"[!] Current URL: {response.url}")
            return True
        elif 'Invalid credentials' in response.text or 'Login' in response.text:
            print("[+] Vulnerability NOT active: Login failed as expected.")
            return False
        else:
            print(f"[?] Unexpected state. URL: {response.url}")
            return False
            
    except Exception as e:
        print(f"[-] Error during login attempt: {e}")
        return False

if __name__ == "__main__":
    try:
        import bs4
    except ImportError:
        print("Installing beautifulsoup4 for HTML parsing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4"])
    
    if test_viewer_bypass():
        sys.exit(1) # Fail if vulnerable
    else:
        sys.exit(0) # Pass if safe

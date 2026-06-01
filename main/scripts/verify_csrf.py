import requests
import re

BASE_URL = "http://127.0.0.1:5000"

def get_csrf_token(session, url):
    response = session.get(url)
    # Search for the CSRF token in the response text using regex
    # Looking for <input ... name="csrf_token" value="TOKEN" ...>
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)
    if match:
        return match.group(1)
    # Also try alternate ordering or quotes just in case
    match = re.search(r'value="([^"]+)"\s+name="csrf_token"', response.text)
    if match:
        return match.group(1)
    return None

def test_csrf_protection():
    session = requests.Session()
    
    # 1. Access Login Page to get CSRF token
    print("Accessing Login Page...")
    login_url = f"{BASE_URL}/login"
    csrf_token = get_csrf_token(session, login_url)
    
    if not csrf_token:
        print("FAIL: Could not find CSRF token on login page.")
        return

    print(f"CSRF Token found: {csrf_token[:10]}...")

    # 2. Attempt Login with Token (Should Succeed or at least not be 400 Bad Request due to CSRF)
    print("Attempting Login with CSRF Token...")
    login_data = {
        'username': 'admin',
        'password': 'password',
        'role': 'Admin',
        'csrf_token': csrf_token
    }
    response = session.post(login_url, data=login_data)
    if response.status_code == 400 and "CSRF" in response.text:
        print("FAIL: Login failed with CSRF error even with token.")
    else:
        print(f"Login with token result: {response.status_code} (Expected not 400)")

    # 3. Attempt Login WITHOUT Token (Should Fail with 400)
    print("Attempting Login WITHOUT CSRF Token...")
    login_data_no_token = {
        'username': 'admin',
        'password': 'password',
        'role': 'Admin'
    }
    response = session.post(login_url, data=login_data_no_token)
    if response.status_code == 400:
        print("PASS: Login blocked without CSRF token (400 Bad Request).")
    else:
        print(f"FAIL: Login succeeded or different error without CSRF token. Status: {response.status_code}")

if __name__ == "__main__":
    try:
        test_csrf_protection()
    except Exception as e:
        print(f"An error occurred: {e}")

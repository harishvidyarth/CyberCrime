import requests
import re
import sys

BASE_URL = 'http://127.0.0.1:5000'
LOGIN_URL = f'{BASE_URL}/login'
UPLOAD_URL = f'{BASE_URL}/upload'
VIEW_ALL_URL = f'{BASE_URL}/view_all_complaints'
EDIT_OFFICER_URL = f'{BASE_URL}/edit_officer/1'
DELETE_COMPLAINT_URL = f'{BASE_URL}/delete_complaint/1'

def get_csrf_token(session):
    try:
        response = session.get(LOGIN_URL)
        # Try finding csrf_token with more flexible regex
        token_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)
        if token_match:
            return token_match.group(1)
        
        print("[-] CSRF token not found in login page. Response snippet:")
        print(response.text[:500]) # Print first 500 chars to debug
        # Search specifically for the input tag to see what it looks like
        if 'csrf_token' in response.text:
             print("Found 'csrf_token' string but regex failed.")
        return None
    except Exception as e:
        print(f"[-] Error getting CSRF token: {e}")
        return None

def verify_viewer_permissions():
    print("[*] Verifying Viewer Permissions...")
    session = requests.Session()
    
    # 1. Login
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
        if response.url.endswith('/index') or 'Welcome' in response.text or 'Dashboard' in response.text:
            print("[+] Login SUCCESSFUL")
        else:
            print("[-] Login FAILED")
            return False
    except Exception as e:
        print(f"[-] Login Error: {e}")
        return False

    # 2. Check View All Complaints
    print("\n[*] Checking View All Complaints access...")
    try:
        resp = session.get(VIEW_ALL_URL)
        if resp.status_code == 200:
            print("[+] View All Complaints: ALLOWED (200 OK)")
        else:
            print(f"[-] View All Complaints: DENIED ({resp.status_code})")
    except Exception as e:
        print(f"[-] Error: {e}")

    # 3. Check Upload Access
    print("\n[*] Checking Upload access...")
    try:
        # Sending empty POST to see if we get 400 (allowed but bad request) or 403 (forbidden)
        # Need CSRF token for upload? Usually yes if CSRF is enabled.
        # But wait, upload might be AJAX or standard form. 
        # app.py has @csrf.exempt? No, it uses CSRFProtect(app).
        # We need to extract CSRF token from the page first?
        # Let's try sending without first, if 400 -> likely allowed but missing file.
        # If 403 -> Forbidden (CSRF or Role).
        # To distinguish, we should include a dummy CSRF token or headers.
        # However, checking if we get "View-only users cannot upload files" message (if it was enabled) is the key.
        # Since we removed that check, we expect standard file validation error.
        
        # We need a fresh CSRF token from the page we are on (index or dashboard)
        # Assuming the session cookie handles it, but we need the token in body or header.
        # Let's try to get it from index.
        resp = session.get(f'{BASE_URL}/index')
        csrf_match = re.search(r'csrf_token" value="([^"]+)"', resp.text)
        token = csrf_match.group(1) if csrf_match else csrf_token

        files = {'file': ('test.xlsx', b'dummy content', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {'csrf_token': token}
        
        resp = session.post(UPLOAD_URL, files=files, data=data)
        
        if resp.status_code == 200:
            print("[+] Upload: SUCCESS (200 OK)")
        elif resp.status_code == 400:
            # 400 is expected if file validation fails (e.g. invalid xlsx content)
            print(f"[+] Upload: ALLOWED but Invalid File (400) - {resp.json().get('error')}")
        elif resp.status_code == 403:
             print(f"[-] Upload: FORBIDDEN (403) - {resp.text}")
        else:
             print(f"[?] Upload: Status {resp.status_code} - {resp.text[:100]}")

    except Exception as e:
        print(f"[-] Error: {e}")

    # 4. Check Edit Officer (Should be BLOCKED)
    print("\n[*] Checking Edit Officer access (Should be BLOCKED)...")
    try:
        resp = session.post(EDIT_OFFICER_URL, json={'password': 'newpassword'}, headers={'X-CSRFToken': token})
        if resp.status_code == 403:
            print("[+] Edit Officer: BLOCKED (403 Forbidden)")
        else:
            print(f"[-] Edit Officer: NOT BLOCKED ({resp.status_code})")
    except Exception as e:
        print(f"[-] Error: {e}")

    # 5. Check Delete Complaint (Should be BLOCKED)
    print("\n[*] Checking Delete Complaint access (Should be BLOCKED)...")
    try:
        resp = session.delete(DELETE_COMPLAINT_URL, headers={'X-CSRFToken': token})
        if resp.status_code == 403:
            print("[+] Delete Complaint: BLOCKED (403 Forbidden)")
        elif resp.status_code == 404:
             # 404 means it tried to find it but failed, meaning it passed auth check?
             # No, delete_complaint checks auth AFTER getting complaint?
             # Let's check code: complaint = Complaint.query.get_or_404(complaint_id) is FIRST.
             # So if ID 1 doesn't exist, we get 404 BEFORE auth check.
             # This is a potential info leak but for this test it means we can't verify auth if ID doesn't exist.
             # We should try to access a protected route that doesn't depend on ID existence first?
             # Or just trust the code review.
             print("[-] Delete Complaint: Returned 404 (Complaint not found). Cannot verify Auth if ID invalid.")
        else:
            print(f"[-] Delete Complaint: Status {resp.status_code}")
            
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    verify_viewer_permissions()

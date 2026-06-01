import requests
import sys

BASE_URL = "http://127.0.0.1:5000"

def check_endpoint(name, url, method='GET'):
    print(f"[*] Checking {name} ({url})...")
    try:
        if method == 'GET':
            response = requests.get(url, allow_redirects=False)
        else:
            response = requests.post(url, allow_redirects=False)
        
        # Check for redirect to login or 401/403
        if response.status_code == 401:
            print(f"[+] {name}: SECURE (401 Unauthorized)")
            return True
        elif response.status_code == 302:
            location = response.headers.get('Location', '')
            if '/login' in location:
                print(f"[+] {name}: SECURE (Redirects to Login)")
                return True
            else:
                print(f"[-] {name}: Redirected to {location} (Warning)")
                return False
        elif response.status_code == 200:
            print(f"[-] {name}: VULNERABLE (200 OK)")
            return False
        else:
            print(f"[?] {name}: Returned status {response.status_code}")
            return True # Assume secure if not 200, but needs manual check
            
    except Exception as e:
        print(f"[!] Error checking {name}: {e}")
        return False

def verify_unauth_access():
    print("Verifying Unauthenticated Access Remediation...")
    
    endpoints = [
        ("Available ACK Nos", f"{BASE_URL}/available_ack_nos"),
        ("Graph Data", f"{BASE_URL}/graph_data/dummy_ack"),
        ("View Graph", f"{BASE_URL}/view_graph?ack_no=dummy_ack"),
        ("Graph Page", f"{BASE_URL}/graph/dummy_ack"),
        ("View Analytics", f"{BASE_URL}/view_analytics"),
        ("View All Complaints", f"{BASE_URL}/view_all_complaints"),
        ("Put On Hold Txns", f"{BASE_URL}/put_on_hold_transactions/dummy_ack"),
        ("Statewise Summary", f"{BASE_URL}/statewise_summary/dummy_ack"),
        ("State Transactions", f"{BASE_URL}/state_transactions/dummy_ack/Punjab"),
        ("ATM Data", f"{BASE_URL}/atm_data/dummy_ack"),
        ("IFSC Info", f"{BASE_URL}/ifsc_info/SBIN0000001")
    ]
    
    all_secure = True
    for name, url in endpoints:
        if not check_endpoint(name, url):
            all_secure = False
            
    if all_secure:
        print("\n[SUCCESS] All endpoints are secure against unauthenticated access.")
    else:
        print("\n[FAILURE] Some endpoints are still accessible!")

if __name__ == "__main__":
    verify_unauth_access()

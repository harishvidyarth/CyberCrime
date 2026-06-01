
import requests
import hashlib
import base64

def verify_sri(url, expected_hash_b64):
    print(f"Verifying {url}...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.content
        
        # Calculate SHA-384 hash
        sha384_hash = hashlib.sha384(content).digest()
        sha384_b64 = base64.b64encode(sha384_hash).decode('utf-8')
        
        if sha384_b64 == expected_hash_b64:
            print(f"PASS: Hash matches for {url}")
            return True
        else:
            print(f"FAIL: Hash mismatch for {url}")
            print(f"  Expected: {expected_hash_b64}")
            print(f"  Actual:   {sha384_b64}")
            return False
    except Exception as e:
        print(f"ERROR: Could not fetch {url}: {e}")
        return False

# Hashes extracted from the updated HTML file
resources = [
    ("https://d3js.org/d3.v7.min.js", "CjloA8y00+1SDAUkjs099PVfnY2KmDC2BZnws9kh8D/lX1s46w6EPhpXdqMfjK6i"),
    ("https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js", "ZZ1pncU3bQe8y31yfZdMFdSpttDoPmOZg2wguVK9almUodir1PghgT0eY7Mrty8H"),
    ("https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.7/pdfmake.min.js", "VFQrHzqBh5qiJIU0uGU5CIW3+OWpdGGJM9LBnGbuIH2mkICcFZ7lPd/AAtI7SNf7"),
    ("https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.7/vfs_fonts.js", "/RlQG9uf0M2vcTw3CX7fbqgbj/h8wKxw7C3zu9/GxcBPRKOEcESxaxufwRXqzq6n")
]

all_passed = True
for url, hash_val in resources:
    if not verify_sri(url, hash_val):
        all_passed = False

if all_passed:
    print("\nSUCCESS: All SRI hashes verified.")
else:
    print("\nFAILURE: Some SRI hashes failed verification.")

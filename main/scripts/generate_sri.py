
import hashlib
import base64
import urllib.request
import ssl

# Ignore SSL certificate errors for this script to ensure we can fetch
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.7/pdfmake.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.7/vfs_fonts.js",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css"
]

print("Calculating SRI hashes...")
for url in urls:
    try:
        with urllib.request.urlopen(url, context=ctx) as response:
            content = response.read()
            hash_obj = hashlib.sha384(content)
            hash_b64 = base64.b64encode(hash_obj.digest()).decode('utf-8')
            print(f"URL: {url}")
            print(f"Integrity: sha384-{hash_b64}")
            print("-" * 20)
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")

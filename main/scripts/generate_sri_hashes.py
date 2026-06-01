import hashlib
import base64
import requests

resources = [
    {
        "url": "https://d3js.org/d3.v7.min.js",
        "file": "templates/graph_tree1.html",
        "name": "d3"
    },
    {
        "url": "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
        "file": "templates/graph_tree1.html",
        "name": "html2canvas"
    },
    {
        "url": "https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.7/pdfmake.min.js",
        "file": "templates/graph_tree1.html",
        "name": "pdfmake"
    },
    {
        "url": "https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.7/vfs_fonts.js",
        "file": "templates/graph_tree1.html",
        "name": "vfs_fonts"
    },
    {
        "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css",
        "file": "templates/view_all_complaints.html",
        "name": "bootstrap"
    }
]

def get_sri_hash(url):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to fetch {url}: {response.status_code}")
            return None
        content = response.content
        hash_obj = hashlib.sha384(content)
        hash_b64 = base64.b64encode(hash_obj.digest()).decode('utf-8')
        return f"sha384-{hash_b64}"
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

for res in resources:
    print(f"Checking {res['name']}...")
    sri = get_sri_hash(res['url'])
    if sri:
        print(f"Resource: {res['name']}")
        print(f"URL: {res['url']}")
        print(f"Integrity: {sri}")
        print("-" * 40)

from app import app
import os
import shutil
import zipfile
import io

def test_zip_download_batch():
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()
    
    ack_no = "TEST_ZIP_BATCH"
    account_numbers = ["111111", "222222", "333333"]
    
    payload = {
        "ack_no": ack_no,
        "account_numbers": account_numbers,
        "letter_type": "suspect",
        "is_poh": True,
        "officer_name": "Officer Z",
        "ncrp_ack_no": ack_no
    }
    
    print(f"Sending batch request for ACK: {ack_no} with accounts: {account_numbers}")
    try:
        res = client.post('/generate_letter_docx', json=payload, follow_redirects=True)
        
        if res.status_code == 200:
            print("Response 200 OK")
            print(f"Content-Type: {res.content_type}")
            print(f"Content-Disposition: {res.headers.get('Content-Disposition')}")
            
            if 'application/zip' in res.content_type:
                print("SUCCESS: Content-Type is application/zip")
                
                # Verify zip content
                try:
                    z = zipfile.ZipFile(io.BytesIO(res.data))
                    print("Zip file opened successfully.")
                    namelist = z.namelist()
                    print("Files in zip:")
                    for name in namelist:
                        print(f" - {name}")
                        
                    # Check for expected structure
                    # Expected: suspect letter/Suspect_Account_Letter_{acc}.docx for all accounts
                    all_found = True
                    for acc in account_numbers:
                        expected_inner = f"suspect letter/Suspect_Account_Letter_{acc}.docx"
                        # Normalize separators
                        found_acc = False
                        for name in namelist:
                            if expected_inner in name.replace('\\', '/'):
                                found_acc = True
                                break
                        if not found_acc:
                            print(f"FAILURE: Missing file for account {acc}")
                            all_found = False
                        else:
                            print(f"Found file for account {acc}")
                    
                    if all_found:
                        print("SUCCESS: All account letters found in the correct folder.")
                    
                except zipfile.BadZipFile:
                    print("FAILURE: Response body is not a valid zip file.")
            else:
                print(f"FAILURE: Content-Type is not application/zip. Got {res.content_type}")
        else:
            print(f"Request failed with {res.status_code}: {res.text}")
    except Exception as e:
        print(f"Test Exception: {e}")

if __name__ == "__main__":
    test_zip_download_batch()

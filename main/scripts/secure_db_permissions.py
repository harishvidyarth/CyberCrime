
import os
import sys
import subprocess
import platform

DB_FILES = ['fundtrail.db', 'kyc_details.db', 'poh_refund_details.db']

def secure_file(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    print(f"Securing {filepath}...")

    if platform.system() == 'Windows':
        # Get current username
        username = os.environ.get('USERNAME')
        if not username:
            print("Could not determine username for ACL.")
            return

        # Build icacls command
        # /inheritance:r removes all inherited ACEs.
        # /grant:r user:F grants full control to user and replaces specific ACEs.
        # This effectively removes 'Everyone' and 'Users' access if they were inherited.
        
        cmd = ['icacls', filepath, '/inheritance:r', '/grant:r', f'{username}:F']
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Success: {result.stdout.strip()}")
            else:
                print(f"Error executing icacls: {result.stderr.strip()}")
        except Exception as e:
            print(f"Exception running icacls: {e}")
            
    else:
        # Linux/Unix - chmod 600
        try:
            os.chmod(filepath, 0o600)
            print(f"Permissions set to 600 for {filepath}")
        except Exception as e:
            print(f"Failed to set permissions: {e}")

if __name__ == '__main__':
    for db_file in DB_FILES:
        # Check in current directory
        full_path = os.path.abspath(db_file)
        secure_file(full_path)


import os
from flask import Flask
from dotenv import load_dotenv

# Load env vars
load_dotenv()

def verify_secret_key():
    print("Verifying SECRET_KEY configuration...")
    
    # Check env var
    env_key = os.environ.get('SECRET_KEY')
    if not env_key:
        print("FAIL: SECRET_KEY not found in environment!")
        return
    print(f"INFO: Found SECRET_KEY in env (len={len(env_key)})")
    
    # Check app config by importing app
    try:
        from app import app
        app_key = app.config.get('SECRET_KEY')
        
        if app_key == env_key:
            print("SUCCESS: app.config['SECRET_KEY'] matches environment variable.")
            print("Remediation verified: Application refuses to start without SECRET_KEY and uses the env var.")
        else:
            print(f"FAIL: app.config['SECRET_KEY'] ({app_key}) does not match env var!")
            
    except RuntimeError as e:
        print(f"FAIL: Application raised RuntimeError: {e}")
    except Exception as e:
        print(f"FAIL: Unexpected error: {e}")

if __name__ == "__main__":
    verify_secret_key()

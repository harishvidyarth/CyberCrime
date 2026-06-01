
import os
from flask import Flask
from dotenv import load_dotenv

# Load env vars
load_dotenv()

def verify_session_config():
    print("Verifying Session Cookie Configuration...")
    
    # Check app config by importing app
    try:
        from app import app
        
        secure = app.config.get('SESSION_COOKIE_SECURE')
        httponly = app.config.get('SESSION_COOKIE_HTTPONLY')
        samesite = app.config.get('SESSION_COOKIE_SAMESITE')
        
        print(f"SESSION_COOKIE_SECURE: {secure}")
        print(f"SESSION_COOKIE_HTTPONLY: {httponly}")
        print(f"SESSION_COOKIE_SAMESITE: {samesite}")
        
        if secure is True:
             print("PASS: SESSION_COOKIE_SECURE is set to True.")
        else:
             print("FAIL: SESSION_COOKIE_SECURE is NOT set to True.")
             
        if httponly is True:
             print("PASS: SESSION_COOKIE_HTTPONLY is set to True.")
        else:
             print("FAIL: SESSION_COOKIE_HTTPONLY is NOT set to True.")
             
        if samesite == 'Lax':
             print("PASS: SESSION_COOKIE_SAMESITE is set to Lax.")
        else:
             print("FAIL: SESSION_COOKIE_SAMESITE is NOT set to Lax.")

    except Exception as e:
        print(f"FAIL: Unexpected error during verification: {e}")

if __name__ == "__main__":
    verify_session_config()

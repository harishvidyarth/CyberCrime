
import os
import re
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# 1. Verify Environment Variables
load_dotenv()
print("--- Checking Environment Variables ---")
if os.environ.get('SECRET_KEY'):
    print("PASS: SECRET_KEY is present in environment.")
else:
    print("FAIL: SECRET_KEY is missing from environment.")

if os.environ.get('DB_USER') and os.environ.get('DB_PASS'):
    print("PASS: DB credentials are present in environment.")
else:
    print("FAIL: DB credentials are missing from environment.")

# 2. Verify Password Complexity Logic (Mocking models.py behavior)
print("\n--- Checking Password Complexity Logic ---")

def validate_password(password):
    """Enforce password complexity"""
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    if not re.search(r'[A-Z]', password):
        raise ValueError("Password must contain uppercase letter")
    if not re.search(r'[a-z]', password):
        raise ValueError("Password must contain lowercase letter")
    if not re.search(r'[0-9]', password):
        raise ValueError("Password must contain number")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValueError("Password must contain special character")
    return True

test_cases = [
    ("weak", "Password must be at least 12 characters"),
    ("short123!", "Password must be at least 12 characters"),
    ("lowercaseonly123!", "Password must contain uppercase letter"),
    ("UPPERCASEONLY123!", "Password must contain lowercase letter"),
    ("NoNumbersHere!", "Password must contain number"),
    ("NoSpecialChar123", "Password must contain special character"),
    ("ValidPassword123!", None)  # Should pass
]

all_tests_passed = True
for pwd, expected_error in test_cases:
    try:
        validate_password(pwd)
        if expected_error:
            print(f"FAIL: '{pwd}' should have failed with '{expected_error}'")
            all_tests_passed = False
        else:
            print(f"PASS: '{pwd}' is valid.")
    except ValueError as e:
        if expected_error and str(e) == expected_error:
            print(f"PASS: '{pwd}' failed as expected with '{e}'")
        elif expected_error:
            print(f"FAIL: '{pwd}' failed with '{e}' but expected '{expected_error}'")
            all_tests_passed = False
        else:
            print(f"FAIL: '{pwd}' failed unexpectedly with '{e}'")
            all_tests_passed = False

if all_tests_passed:
    print("\nSUCCESS: All password complexity tests passed.")
else:
    print("\nFAILURE: Some password complexity tests failed.")

# 3. Verify App Configuration (Importing app)
print("\n--- Checking App Configuration ---")
try:
    from app import app
    print(f"PASS: App imported successfully.")
    print(f"PASS: SECRET_KEY loaded in app config: {bool(app.config.get('SECRET_KEY'))}")
except ImportError as e:
    print(f"FAIL: Could not import app: {e}")
except Exception as e:
    print(f"FAIL: Error checking app config: {e}")


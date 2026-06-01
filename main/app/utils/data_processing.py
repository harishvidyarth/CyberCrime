import re
import pandas as pd
import requests
import json
import os
import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

# IFSC Constants
ALLOWED_IFSC_DOMAIN = 'ifsc.razorpay.com'
IFSC_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'ifsc_state_cache.json')
ifsc_api_cache = {}

def load_ifsc_cache():
    global ifsc_api_cache
    if os.path.exists(IFSC_CACHE_FILE):
        try:
            with open(IFSC_CACHE_FILE, 'r') as f:
                ifsc_api_cache = json.load(f)
            logger.info(f"Loaded {len(ifsc_api_cache)} entries from IFSC cache.")
        except Exception as e:
            logger.error(f"Error loading IFSC cache: {e}")
            ifsc_api_cache = {}
    return ifsc_api_cache

def save_ifsc_cache():
    try:
        with open(IFSC_CACHE_FILE, 'w') as f:
            json.dump(ifsc_api_cache, f)
        logger.info(f"Saved {len(ifsc_api_cache)} entries to IFSC cache.")
    except Exception as e:
        logger.error(f"Error saving IFSC cache: {e}")

def get_state_from_api(ifsc_code):
    if not ifsc_code or ifsc_code == 'N/A':
        return 'Unknown'

    if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc_code):
        return 'Invalid IFSC'

    if ifsc_code in ifsc_api_cache:
        return ifsc_api_cache[ifsc_code]

    try:
        from ifsc_utils import get_state as get_state_local
        local_state = get_state_local(ifsc_code)
        if local_state and local_state != 'Unknown':
            ifsc_api_cache[ifsc_code] = local_state
            return local_state
    except Exception as e:
        logger.error(f"Error fetching state from local utils for {ifsc_code}: {e}")

    try:
        url = f'https://{ALLOWED_IFSC_DOMAIN}/{ifsc_code}'
        response = requests.get(url, timeout=5, allow_redirects=False)
        if response.status_code == 200:
            data = response.json()
            state = data.get('STATE', 'Unknown')
            ifsc_api_cache[ifsc_code] = state
            return state
        return 'Unknown'
    except Exception as e:
        logger.error(f"Error fetching state for {ifsc_code}: {e}")
        return 'Unknown'

def clean_amount(value):
    if pd.isna(value): return 0.0
    try: return float(str(value).replace(',', '').strip())
    except: return 0.0

def validate_account_number(account):
    if not account or account == 'N/A':
        return True
    return bool(re.match(r'^\d{9,18}$', str(account)))

def validate_amount(amount):
    try:
        amt = Decimal(str(amount))
        return amt > 0 and amt < Decimal('999999999.99')
    except (InvalidOperation, ValueError):
        return False

def ordinal(n):
    try:
        n = int(n)
    except Exception:
        return str(n)
    if 10 <= n % 100 <= 20:
        suf = 'th'
    else:
        suf = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suf}"

def format_indian_currency(amount):
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return "0.00"
    s = "{:.2f}".format(amount)
    parts = s.split('.')
    integer_part = parts[0]
    if len(integer_part) > 3:
        last_three = integer_part[-3:]
        rest = integer_part[:-3]
        rest_formatted = ""
        while len(rest) > 2:
            rest_formatted = "," + rest[-2:] + rest_formatted
            rest = rest[:-2]
        rest_formatted = rest + rest_formatted
        integer_part = rest_formatted + "," + last_three
    return f"₹{integer_part}"

def sanitize_cell(value):
    if isinstance(value, str):
        if value.startswith(('=', '+', '-', '@', '\t', '\r')):
            return "'" + value
    return value

def clean_bank_name(value):
    if pd.isna(value) or value is None:
        return ''
    s = str(value).strip()
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\s+', ' ', s)
    s = s.strip()
    if len(s) > 100:
        s = s[:100]
    return s

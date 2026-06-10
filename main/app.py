from flask import Flask, render_template, request, redirect, session, url_for, flash, send_file, jsonify, abort, send_from_directory, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from functools import wraps
from dotenv import load_dotenv
import secrets
import time
import string

load_dotenv()
import hmac
from urllib.parse import urlparse, urljoin
from flask_sqlalchemy import SQLAlchemy
from collections import defaultdict
import os
import io
import json
import zipfile
import contextlib
if os.name == 'nt':
    import msvcrt
else:
    import fcntl
from models import db, User, Transaction, UploadedFile, Complaint, UsageLog, POHRefundDetails, KYCDetails
import pandas as pd  # pyright: ignore[reportMissingImports]
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_required, LoginManager, login_user, logout_user, current_user  # pyright: ignore[reportMissingImports]
from flask_wtf.csrf import CSRFProtect, CSRFError
from datetime import timezone, timedelta, datetime
from sqlalchemy import func, desc, inspect, text, or_
from sqlalchemy.orm import defer
from flask_migrate import Migrate  # pyright: ignore[reportMissingModuleSource]
import pymysql  # pyright: ignore[reportMissingModuleSource]
pymysql.install_as_MySQLdb()
import concurrent.futures
import re
from decimal import Decimal, InvalidOperation
import requests
import sys
import logging
from logging.handlers import RotatingFileHandler
from xhtml2pdf import pisa
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ReportLab imports for PDF generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# log file location
if os.name == 'nt':
    log_dir = os.path.join(os.environ.get('APPDATA'), 'FundTrailTool')
else:
    log_dir = os.path.join(os.path.expanduser('~'), '.fundtrailtool')

os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, 'app.log')

handler = RotatingFileHandler(log_file_path, maxBytes=10000000, backupCount=5)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS   # PyInstaller
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))  # normal run
    return os.path.join(base_path, relative_path)

app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static")
)

try:
    from werkzeug.serving import WSGIRequestHandler
    WSGIRequestHandler.server_version = ""
    WSGIRequestHandler.sys_version = ""
except Exception:
    pass

class StripServerHeaderMiddleware:
    def __init__(self, app):
        self.app = app
    def __call__(self, environ, start_response):
        def custom_start_response(status, headers, exc_info=None):
            filtered = [(k, v) for (k, v) in headers if k.lower() not in ('server', 'x-powered-by', 'x-aspnet-version', 'x-aspnetmvc-version')]
            return start_response(status, filtered, exc_info)
        return self.app(environ, custom_start_response)

app.wsgi_app = StripServerHeaderMiddleware(app.wsgi_app)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

@app.before_request
def generate_csp_nonce():
    """Generate a random nonce for CSP"""
    g.csp_nonce = secrets.token_hex(16)

@app.context_processor
def inject_csp_nonce():
    """Inject CSP nonce into templates"""
    return dict(csp_nonce=g.csp_nonce)

@app.after_request
def set_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # Remove Server header to prevent information disclosure
    response.headers.pop('Server', None)
    
    # Use the nonce generated in before_request
    nonce = getattr(g, 'csp_nonce', '')
    
    csp_policy = (
        "default-src 'self'; "
        f"script-src 'self' https://d3js.org 'nonce-{nonce}'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    
    response.headers['Content-Security-Policy'] = csp_policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    
    # Remove Server header to prevent version disclosure (FT-09)
    response.headers.pop('Server', None)
    
    # Prevent caching of sensitive pages (FT-012)
    if 'static' not in request.path.lower():
        if 'Cache-Control' not in response.headers:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    return response

csrf = CSRFProtect(app)


migrate = Migrate(app, db)

# Cache for IFSC to state mappings to avoid repeated API calls
ifsc_cache = {}

# IFSC district code to state mapping
DISTRICT_TO_STATE = {
    '01': 'Jammu and Kashmir',
    '02': 'Himachal Pradesh',
    '03': 'Punjab',
    '04': 'Chandigarh',
    '05': 'Uttarakhand',
    '06': 'Haryana',
    '07': 'Delhi',
    '08': 'Rajasthan',
    '09': 'Uttar Pradesh',
    '10': 'Bihar',
    '11': 'Sikkim',
    '12': 'Arunachal Pradesh',
    '13': 'Nagaland',
    '14': 'Manipur',
    '15': 'Mizoram',
    '16': 'Tripura',
    '17': 'Meghalaya',
    '18': 'Assam',
    '19': 'West Bengal',
    '20': 'Jharkhand',
    '21': 'Odisha',
    '22': 'Chhattisgarh',
    '23': 'Madhya Pradesh',
    '24': 'Gujarat',
    '25': 'Daman and Diu',
    '26': 'Dadra and Nagar Haveli',
    '27': 'Maharashtra',
    '28': 'Andhra Pradesh',
    '29': 'Karnataka',
    '30': 'Goa',
    '31': 'Lakshadweep',
    '32': 'Kerala',
    '33': 'Tamil Nadu',
    '34': 'Puducherry',
    '35': 'Andaman and Nicobar Islands',
    '36': 'Telangana',
    '37': 'Andhra Pradesh',
    '38': 'Ladakh'
}

def get_state(ifsc):
    if not ifsc or len(ifsc) < 6:
        return 'Unknown'
    if ifsc in ifsc_cache:
        return ifsc_cache[ifsc]
    district_code = ifsc[4:6]
    state = DISTRICT_TO_STATE.get(district_code)
    if state:
        ifsc_cache[ifsc] = state
        return state
    # Fallback to local IFSC_CODES.xlsx lookup

def check_case_access(ack_no):
    """
    Verifies if the current user has access to the case identified by ack_no.
    Aborts with 403 if unauthorized.
    """
    if not current_user.is_authenticated:
        abort(403)

    # Admin and Viewer can access all cases
    if current_user.role in ['Admin']:
        return

    ack_no = str(ack_no).strip()
    complaint = Complaint.query.filter_by(ack_no=ack_no).first()

    if complaint:
        # If case is explicitly assigned or uploaded by this officer, allow
        if complaint.assigned_to == current_user.id or complaint.uploaded_by == current_user.id:
            return
        # If complaint exists but is unassigned, allow read-only access to officers
        if complaint.assigned_to is None:
            return
    else:
        # If there is no complaint yet but transactions exist for this ACK,
        # allow officers to view the graph (read-only analytics)
        has_txn = Transaction.query.filter_by(ack_no=ack_no).first()
        if has_txn:
            return

    logger.warning(f"Unauthorized access attempt to resource {ack_no} by {current_user.username}")
    abort(403)

    try:
        from ifsc_utils import get_state as excel_get_state
        state = excel_get_state(ifsc)
        if state and state != 'Unknown':
            ifsc_cache[ifsc] = state
            return state
    except Exception as e:
        logger.error(f"Error fetching state for IFSC from excel {ifsc}: {e}")
    ifsc_cache[ifsc] = 'Unknown'
    return 'Unknown'


def validate_password(password):
    """Enforce password complexity"""
    if len(password) < 12:
        return False, "Password must be at least 12 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain number"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain special character"
    return True, "Valid"

# Note: The User model in models.py has its own validate_password function that raises ValueError.
# This one is kept if needed for other checks, but we should align them.
# For now, we rely on User.set_password to enforce complexity.

ALLOWED_IFSC_DOMAIN = 'ifsc.razorpay.com'
MAX_WORKERS = 10
IFSC_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ifsc_state_cache.json')
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
    else:
        ifsc_api_cache = {}

def save_ifsc_cache():
    try:
        with open(IFSC_CACHE_FILE, 'w') as f:
            json.dump(ifsc_api_cache, f)
        logger.info(f"Saved {len(ifsc_api_cache)} entries to IFSC cache.")
    except Exception as e:
        logger.error(f"Error saving IFSC cache: {e}")

# Initialize cache
load_ifsc_cache()

def get_state_from_api(ifsc_code):
    if not ifsc_code or ifsc_code == 'N/A':
        return 'Unknown'

    # Validate IFSC format (11 alphanumeric characters)
    if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc_code):
        return 'Invalid IFSC'

    if ifsc_code in ifsc_api_cache:
        return ifsc_api_cache[ifsc_code]

    # Try local Excel/Pickle first
    try:
        from ifsc_utils import get_state as get_state_local
        local_state = get_state_local(ifsc_code)
        if local_state and local_state != 'Unknown':
            ifsc_api_cache[ifsc_code] = local_state
            return local_state
    except Exception as e:
        logger.error(f"Error fetching state from local utils for {ifsc_code}: {e}")

    try:
        # Use only trusted API endpoint
        url = f'https://{ALLOWED_IFSC_DOMAIN}/{ifsc_code}'
        response = requests.get(url, timeout=5, allow_redirects=False)
        
        if response.status_code == 200:
            data = response.json()
            state = data.get('STATE', 'Unknown')
            ifsc_api_cache[ifsc_code] = state
            return state
        else:
            return 'Unknown'
    except Exception as e:
        logger.error(f"Error fetching state for {ifsc_code}: {e}")
        return 'Unknown'


@app.route('/ifsc_info/<ifsc>')
@login_required
def ifsc_info(ifsc):
    try:
        from ifsc_utils import get_ifsc_info
        info = get_ifsc_info(ifsc) or {}
        return jsonify(info)
    except Exception as e:
        logger.error(f"Error returning IFSC info for {ifsc}: {e}")
        return jsonify({}), 500

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # redirect to this route if not logged in

# Tell Flask-Login how to load a user
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def _is_posix():
    return os.name != 'nt'

def _ensure_secure_dir(path):
    os.makedirs(path, exist_ok=True)
    if _is_posix():
        try:
            os.chmod(path, 0o700)
        except Exception:
            pass

def _ensure_secure_file(path):
    if not os.path.exists(path):
        with open(path, 'a'):
            pass
    if _is_posix():
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass

# FT-006 (Weak/Hardcoded Secret Key): the key MUST come from the environment.
# There is deliberately NO hardcoded fallback — the app refuses to start without
# a real secret. This restores the behaviour verified in the Feb-2026 security
# retest. Do NOT re-add a fallback string here (that was the regression we fixed).
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable not set! Generate one with: "
        "python3 -c \"import secrets; print(secrets.token_hex(32))\" "
        "and add it to your .env file."
    )
app.config['SECRET_KEY'] = SECRET_KEY
secure_base = os.environ.get('FUNDTRAIL_DATA_DIR')
if not secure_base:
    secure_base = os.path.join(os.path.dirname(app.root_path), 'data')
_ensure_secure_dir(secure_base)
primary_db_path = os.path.join(secure_base, 'fundtrail.db')
poh_db_path = os.path.join(secure_base, 'poh_refund_details.db')
kyc_db_path = os.path.join(secure_base, 'kyc_details.db')
_ensure_secure_file(primary_db_path)
_ensure_secure_file(poh_db_path)
_ensure_secure_file(kyc_db_path)
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    db_url = f"sqlite:///{primary_db_path}"
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_BINDS'] = {
    'poh_store': f'sqlite:///{poh_db_path}',
    'kyc_store': f'sqlite:///{kyc_db_path}'
}

# Secure session cookie configuration.
# FT-010: the Secure flag MUST be True in production (HTTPS). But over plain http
# (local dev / offline http://127.0.0.1) browsers never send a Secure cookie, which
# silently breaks login. So we default to True (secure) and allow an explicit,
# documented opt-out for local development only.
#   -> set SESSION_COOKIE_INSECURE=true in .env ONLY on a local dev machine.
_cookie_insecure = os.environ.get('SESSION_COOKIE_INSECURE', 'false').lower() == 'true'
app.config['SESSION_COOKIE_SECURE'] = not _cookie_insecure  # True unless explicitly opted out

app.config['SESSION_COOKIE_HTTPONLY'] = True # No JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' # CSRF protection
# Removed __Host- prefix as it requires Secure=True (HTTPS)
app.config['SESSION_COOKIE_NAME'] = 'session'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_REFRESH_EACH_REQUEST'] = False
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

def ensure_usage_log_table():
    inspector = inspect(db.engine)
    if 'usage_log' not in inspector.get_table_names():
        db.create_all()

def log_usage(action, filename=None, ack_no=None):
    try:
        entry = UsageLog(
            username=session.get('username'),
            role=session.get('role'),
            action=action,
            filename=filename,
            ack_no=ack_no
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.error(f"UsageLog error: {e}")

def validate_account_number(account):
    """Validate account number format"""
    if not account or account == 'N/A':
        return True
    return bool(re.match(r'^\d{9,18}$', str(account)))

def validate_amount(amount):
    """Validate transaction amount"""
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

def ensure_transaction_columns():
    """Add any newly introduced columns to the transaction table if missing."""
    required_columns = {
        'layer': 'INT',
        'from_account': 'VARCHAR(100)',
        'to_account': 'VARCHAR(100)',
        'ack_no': 'VARCHAR(100)',
        'bank_name': 'VARCHAR(100)',
        'ifsc_code': 'VARCHAR(50)',
        'txn_date': 'VARCHAR(100)',
        'txn_id': 'VARCHAR(100)',
        'amount': 'FLOAT',
        'disputed_amount': 'FLOAT',
        'action_taken': 'VARCHAR(255)',
        'account_number': 'VARCHAR(50)',
        'state': 'VARCHAR(50)',
        'atm_id': 'VARCHAR(100)',
        'atm_withdraw_amount': 'FLOAT',
        'atm_withdraw_date': 'VARCHAR(100)',
        'atm_location': 'VARCHAR(200)',
        'cheque_no': 'VARCHAR(100)',
        'cheque_withdraw_amount': 'FLOAT',
        'cheque_withdraw_date': 'VARCHAR(100)',
        'cheque_ifsc': 'VARCHAR(50)',
        'put_on_hold_txn_id': 'VARCHAR(100)',
        'put_on_hold_date': 'VARCHAR(100)',
        'put_on_hold_amount': 'FLOAT',
        'court_order_date': 'VARCHAR(20)',
        'refund_status': 'VARCHAR(50)',
        'refund_amount': 'FLOAT',
        'kyc_name': 'VARCHAR(120)',
        'kyc_aadhar': 'VARCHAR(20)',
        'kyc_mobile': 'VARCHAR(20)',
        'kyc_address': 'VARCHAR(200)',
        'upload_id': 'INT'
    }

    # Only run MySQL-specific ALTERs when using a MySQL driver
    try:
        driver = db.engine.url.drivername
    except Exception:
        driver = ''
    if driver.startswith('mysql'):
        inspector = inspect(db.engine)
        if inspector.has_table('transaction'):
            with db.engine.connect() as conn:
                for col, ddl in required_columns.items():
                    result = conn.execute(
                        text("SHOW COLUMNS FROM `transaction` LIKE :column_name"),
                        {"column_name": col}
                    )
                    if not result.fetchone():
                        try:
                            conn.execute(text(f'ALTER TABLE `transaction` ADD COLUMN `{col}` {ddl}'))
                            logger.info(f"Added missing column: {col}")
                        except Exception as exc:
                            logger.warning(f"Skipping column {col}; encountered error: {exc}")

def ensure_user_columns():
    """Add newly introduced columns to the user table if they are missing."""
    required_columns = {
        'name': 'VARCHAR(100)',
        'rank': 'VARCHAR(100)',
        'email': 'VARCHAR(120)',
        'manual_upload_count': 'INT NULL',
        'must_change_password': 'BOOLEAN DEFAULT 0'
    }

    # Only run MySQL-specific ALTERs when using a MySQL driver
    try:
        driver = db.engine.url.drivername
    except Exception:
        driver = ''
    if driver.startswith('mysql'):
        inspector = inspect(db.engine)
        if inspector.has_table('user'):
            with db.engine.connect() as conn:
                for col, ddl in required_columns.items():
                    result = conn.execute(
                        text("SHOW COLUMNS FROM `user` LIKE :column_name"),
                        {"column_name": col}
                    )
                    if not result.fetchone():
                        try:
                            if col not in required_columns:
                                raise ValueError(f"Invalid column name: {col}")
                            conn.execute(text(f'ALTER TABLE `user` ADD COLUMN `{col}` {ddl}'))
                            logger.info(f"Added missing user column: {col}")
                        except Exception as exc:
                            logger.warning(f"Skipping user column {col}; encountered error: {exc}")

def generate_secure_password(length=16):
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*(),.?":{}|<>'
    while True:
        password = ''.join(secrets.choice(alphabet) for i in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in '!@#$%^&*(),.?":{}|<>' for c in password)):
            return password

def initialize_secure_users():
    """Initialize users with secure random passwords if they don't exist."""
    
    # Check if any users exist to avoid re-initialization
    if User.query.first():
        return

    logger.info("Initializing users with secure random passwords...")
    
    users_to_create = [
        ('admin', 'Admin'),
        ('officer', 'Investigative Officer')
    ]
    
    created_credentials = []
    
    for username, role in users_to_create:
        if not User.query.filter_by(username=username).first():
            password = generate_secure_password()
            user = User(username=username, role=role)
            user.set_password(password)
            # Ensure the user model has this attribute or handle it if it's dynamic
            # We added the column to ensure_user_columns, so it should be fine in DB
            # But the ORM model (models.py) might not have it mapped yet.
            # However, we can set it on the instance if it's in the DB schema? 
            # No, SQLAlchemy needs the field in the model class.
            # We'll assume models.py needs update or we use raw SQL if model not updated?
            # Ideally update models.py too. But for now let's set it.
            user.must_change_password = True
            db.session.add(user)
            created_credentials.append((username, password))
            logger.info(f"User '{username}' created.")
            
    db.session.commit()
    
    if created_credentials:
        print("\n" + "="*60)
        print("SECURITY NOTICE: INITIAL PASSWORDS GENERATED")
        print("="*60)
        for username, pwd in created_credentials:
            print(f"User: {username:<15} Password: {pwd}")
        print("="*60)
        print("Please copy these credentials immediately. They will not be shown again.")
        print("You will be required to change the password on first login.\n")

with app.app_context():
    ensure_transaction_columns()
    ensure_user_columns()
    ensure_usage_log_table()



VIEW_ONLY_ROLES = set()  # Viewer (read-only) role removed — only Admin & Investigative Officer

@app.route('/')
def home():
    return redirect('/login')

@app.route('/home')
def role_home():
    """Single 'Home' entry point. Always sends a user to THEIR OWN dashboard, so an
    admin never lands on the officer dashboard (and vice-versa). Generic 'Return to
    Home' links point here instead of hard-coding one dashboard."""
    if 'username' not in session:
        return redirect(url_for('login'))
    if session.get('role') == 'Admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('index'))

ALLOWED_HOSTS = {'localhost', '127.0.0.1', '0.0.0.0'}

def is_safe_url(target):
    if not target:
        return False
    # Only allow relative URLs starting with /
    if target.startswith('/') and not target.startswith('//'):
        return True
    parsed = urlparse(target)
    return parsed.netloc in ALLOWED_HOSTS and parsed.scheme in ('http', 'https')

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    # Accessible voluntarily by any logged-in user, OR forced when
    # must_change_password is True (e.g. first login after admin creates account).
    forced = getattr(current_user, 'must_change_password', False)
    error  = None

    if request.method == 'POST':
        current_pw  = request.form.get('current_password', '')
        new_pw      = request.form.get('new_password', '')
        confirm_pw  = request.form.get('confirm_password', '')

        # 1. Verify the user knows their present password
        if not current_user.check_password(current_pw):
            error = "Current password is incorrect."
        elif new_pw != confirm_pw:
            error = "New passwords do not match."
        elif new_pw == current_pw:
            error = "New password must be different from your current password."
        else:
            try:
                current_user.set_password(new_pw)   # also validates complexity
                current_user.must_change_password = False
                db.session.commit()
                log_usage('change_password')
                flash("Password changed successfully.", "success")
                # Forced change → log out so they re-authenticate with new password
                if forced:
                    logout_user()
                    return redirect(url_for('login'))
                # Voluntary change → stay logged in, return to their dashboard
                role = session.get('role', '')
                return redirect(url_for('admin_dashboard') if role == 'Admin' else url_for('index'))
            except ValueError as e:
                error = str(e)

    return render_template('change_password.html', error=error, forced=forced)

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    error = None
    if request.method == 'POST':
        # Use .get() to avoid KeyError when viewer fields are disabled
        role = request.form.get('role', '').strip()

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Standard login flow for all roles
        # Always perform password check to prevent timing attack
        user = User.query.filter_by(username=username, role=role).first()

        
        if user:
            # Check if account is locked (ensure timezone awareness for comparison)
            if user.account_locked_until:
														   
                lock_time = user.account_locked_until.replace(tzinfo=timezone.utc) if user.account_locked_until.tzinfo is None else user.account_locked_until
                now_time = datetime.now(timezone.utc)
                if lock_time > now_time:
                    remaining = int((lock_time - now_time).total_seconds() / 60)
                    flash(f'Account locked. Try again in {remaining} minutes.')
                    return redirect(url_for('login'))

        password_valid = False
        if user:
            password_valid = user.check_password(password)
        else:

            # Perform dummy hash operation to maintain consistent timing
            # We use a dummy hash that matches the algorithm used in check_password
            dummy_hash = generate_password_hash('dummy_password')
            check_password_hash(dummy_hash, password)
            password_valid = False

        # Constant-time comparison logic (logically, though Python's bool comparison isn't strictly constant-time, the heavy lifting is the hash)
        if user and password_valid:
            # Reset failed attempts on successful login
            user.failed_login_attempts = 0
            user.account_locked_until = None
            db.session.commit()

            # Establish Flask-Login session
            login_user(user)

            session['username'] = username
            session['role'] = role
            log_usage('login')
            
            # Enforce password change if required
            if getattr(user, 'must_change_password', False):
                return redirect(url_for('change_password'))
            
            next_page = request.args.get('next')
            
            # Validate redirect URL
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            else:
                return redirect('/admin_dashboard') if role == 'Admin' else redirect('/index')
        else:
            if user:
                # Increment failed attempts
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                
                if user.failed_login_attempts >= 5:
                    user.account_locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                    flash('Account locked for 15 minutes due to multiple failed attempts.')
                else:
                    flash(f'Invalid credentials. {5 - user.failed_login_attempts} attempts remaining.')
                
                db.session.commit()
            
            # Add small random delay (100-300ms) to mask any remaining timing differences
            time.sleep(0.1 + (hash(username) % 200) / 1000.0)
            error = "Invalid credentials or role"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    log_usage('logout')
    logout_user()
    session.clear()
    return redirect('/login')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' in session and session['role'] == 'Admin':
        return render_template('admin_dashboard.html', username=session['username'])
    else:
        return redirect(url_for('login'))


@app.route('/index')
def index():
    if 'username' not in session:
        return redirect('/login')
    # Strict role separation: the admin has their own dashboard. If an admin reaches
    # the officer dashboard, bounce them back to the admin dashboard.
    if session.get('role') == 'Admin':
        return redirect(url_for('admin_dashboard'))
    return render_template('index.html')

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
MAX_FILE_SIZE = 50 * 1024 * 1024 # 50MB
MAX_ROWS = 100000  # Increased limit to support larger files

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@contextlib.contextmanager
def file_lock(filepath):
    """Context manager for file locking (Cross-platform)"""
    lock_file = f"{filepath}.lock"
    # Create lock file if it doesn't exist
    lock_fd = os.open(lock_file, os.O_RDWR | os.O_CREAT | os.O_TRUNC)
    try:
        if os.name == 'nt':
            # Windows: Blocking lock for 10 attempts (approx 10s)
            msvcrt.locking(lock_fd, msvcrt.LK_RLCK, 1)
        else:
            # Unix: Exclusive blocking lock
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        
        yield
    finally:
        # Unlock and clean up
        if os.name == 'nt':
            msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        
        os.close(lock_fd)
        try:
            os.remove(lock_file)
        except OSError:
            pass

@app.route('/upload', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def upload_file():
    # Allow Viewer to upload files
    # if session.get('role') in VIEW_ONLY_ROLES:
    #     return jsonify({'error': 'View-only users cannot upload files.'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Validate file extension
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only .xlsx and .xls allowed'}), 400

    try:
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': 'File too large. Maximum 10MB'}), 400

        # Generate secure filename
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{secrets.token_hex(16)}.{ext}"

        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'message': 'File uploaded successfully', 'filename': filename}), 200
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to process file. Please check format.'}), 500

@app.route('/upload_excel', methods=['POST'])
@login_required
def upload_excel():
    # Allow Viewer to upload complaints
    # if session.get('role') in VIEW_ONLY_ROLES:
    #     flash("View-only users cannot upload complaints.", "warning")
    #     return redirect('/index')

    file = request.files['excel_file']
    if not file or not file.filename.endswith('.xlsx'):
        flash("Invalid file format. Please upload a .xlsx file.", "warning")
        return redirect('/index')

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # Use file lock to prevent race conditions
    with file_lock(file_path):
        # Check for duplicate filename
        existing_file = UploadedFile.query.filter_by(filename=filename).first()
        if existing_file:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                # Remove old file if it exists
                if os.path.exists(old_path):
                    os.remove(old_path)
            except OSError as e:
                logger.warning(f"Failed to delete old file {old_path}: {e}")
            
            # Delete associated transactions first
            try:
                Transaction.query.filter_by(upload_id=existing_file.id).delete()
            except Exception as e:
                logger.error(f"Error deleting associated transactions for file {filename}: {e}")

            # Delete database record
            db.session.delete(existing_file)
            db.session.commit()
            logger.info(f"Existing file and record deleted: {filename}")

    file.save(file_path)

    try:
        # ✅ Step 2: Read Excel and extract acknowledgment numbers
        
        # Helper for sanitizing cell values to prevent CSV/Excel injection
        def sanitize_cell(value):
            """Remove formula injection characters"""
            if isinstance(value, str):
                if value.startswith(('=', '+', '-', '@', '\t', '\r')):
                    return "'" + value # Prefix with quote to neutralize
            return value

        try:
            xls = pd.ExcelFile(file_path, engine='openpyxl')
        except Exception as e:
            logger.error(f"Error reading Excel file: {str(e)}", exc_info=True)
            flash("Error reading Excel file. Please ensure it is a valid .xlsx file.", "error")
            return redirect('/index')

        # Robustly find the sheet name (handles case/spacing/extra text)
        def find_sheet_name(xls_obj, target):
            names = xls_obj.sheet_names or []
            # Exact match first
            if target in names:
                return target
            # Trim & case-insensitive
            for n in names:
                if n and n.strip().lower() == target.strip().lower():
                    return n
            # Containment (target inside sheet name)
            for n in names:
                if n and target.strip().lower() in n.strip().lower():
                    return n
            # Normalize non-alphanum and compare
            def simple(s):
                return re.sub(r'[^0-9a-z]+', '', str(s).lower())
            t_simple = simple(target)
            for n in names:
                if simple(n) == t_simple:
                    return n
            return None

        sheet_name = find_sheet_name(xls, 'Money Transfer to')
        if not sheet_name:
            available = ", ".join([f"'{s}'" for s in (xls.sheet_names or [])])
            raise ValueError(f"Worksheet named 'Money Transfer to' not found. Available sheets: {available}")

        tx_df = pd.read_excel(xls, sheet_name=sheet_name)
        
        # Check row count
        if len(tx_df) > MAX_ROWS:
            xls.close()
            if os.path.exists(file_path):
                os.remove(file_path)
            flash(f"File contains too many rows. Maximum {MAX_ROWS} rows allowed.", "error")
            return redirect('/index')

        # Sanitize all cells in main dataframe
        for col in tx_df.columns:
            tx_df[col] = tx_df[col].apply(sanitize_cell)

        acknos_in_excel = tx_df['Acknowledgement No.'].dropna().unique()

        if len(acknos_in_excel) == 0:
            flash("⚠️ No Acknowledgement numbers found in the Excel file!", "warning")
            return redirect('/index')

        # ✅ Step 3: Purge ALL existing transactions for these ACK numbers.
        # This is belt-and-suspenders: the filename-dedup above handles same-name
        # re-uploads, but this catches any lingering rows from a differently-named
        # copy of the same data (which would otherwise double every amount shown).
        existing_acks = Transaction.query.filter(
            Transaction.ack_no.in_(acknos_in_excel)
        ).all()
        if existing_acks:
            # Bulk-delete is faster and avoids per-object overhead
            Transaction.query.filter(
                Transaction.ack_no.in_(acknos_in_excel)
            ).delete(synchronize_session='fetch')
            db.session.commit()
            flash("ℹ️ Existing records for these ACK numbers replaced.", "info")

        # Re-read file to get binary data for storage
        with open(file_path, 'rb') as f:
            file_data = f.read()

        uploaded_file = UploadedFile(
            filename=filename,
            data=file_data,
            uploader=session.get('username'),
            mimetype=file.mimetype
        )
        db.session.add(uploaded_file)
        db.session.commit()
        log_usage('upload_excel', filename=filename)

        # ✅ Step 5: Process and insert transactions
        atm_df = pd.read_excel(xls, sheet_name='Withdrawal through ATM') if 'Withdrawal through ATM' in xls.sheet_names else pd.DataFrame()
        chq_df = pd.read_excel(xls, sheet_name='Cash Withdrawal through Cheque') if 'Cash Withdrawal through Cheque' in xls.sheet_names else pd.DataFrame()
        hold_df = pd.read_excel(xls, sheet_name='Transaction put on hold') if 'Transaction put on hold' in xls.sheet_names else pd.DataFrame()

        # Sanitize additional dataframes
        if not atm_df.empty:
            for col in atm_df.columns:
                atm_df[col] = atm_df[col].apply(sanitize_cell)
        
        if not chq_df.empty:
            for col in chq_df.columns:
                chq_df[col] = chq_df[col].apply(sanitize_cell)

        if not hold_df.empty:
            for col in hold_df.columns:
                hold_df[col] = hold_df[col].apply(sanitize_cell)

        def normalize_columns(df):
            return [str(c).encode('ascii', 'ignore').decode().strip().replace('\u00A0', ' ').replace('\xa0', ' ') for c in df.columns]

        # Normalize all dataframe columns for consistent matching
        tx_df.columns = normalize_columns(tx_df)
        if not atm_df.empty: atm_df.columns = normalize_columns(atm_df)
        if not chq_df.empty: chq_df.columns = normalize_columns(chq_df)
        if not hold_df.empty: hold_df.columns = normalize_columns(hold_df)
        
        # DEBUG: Log all columns in Excel
        logger.debug("[UPLOAD DEBUG] All columns in 'Money Transfer to' sheet:")
        for i, col in enumerate(tx_df.columns):
            logger.debug(f"  {i}: '{col}'")
        
        # DEBUG: Log presence of data (without sensitive details)
        if not tx_df.empty:
            logger.debug(f"[UPLOAD DEBUG] First row data present. Columns: {list(tx_df.columns)}")

        def clean_amount(value):
            if pd.isna(value): return 0.0
            try: return float(str(value).replace(',', '').strip())
            except: return 0.0

        def clean_location(value):
            """Normalize ATM location strings and strip common prefixes."""
            if pd.isna(value) or value is None:
                return None
            s = str(value).strip()
            prefixes = [
                "Place of ATM :-",
                "Place of ATM :",
                "Place/Location of ATM :",
                "Place/Location of ATM",
                "Place / Location of ATM",
                "Place of ATM",
                "Place/Location",
            ]
            for p in prefixes:
                if s.lower().startswith(p.lower()):
                    s = s[len(p):].strip(" :-")
                    break
            return s or None

        def clean_bank_name(value):
            """Clean bank name by removing HTML tags and truncating to 100 characters."""
            if pd.isna(value) or value is None:
                return ''
            # Convert to string and strip whitespace
            s = str(value).strip()
            # Remove HTML tags (e.g., <hr/>, <br/>, etc.)
            s = re.sub(r'<[^>]+>', '', s)
            # Replace multiple spaces with single space
            s = re.sub(r'\s+', ' ', s)
            # Strip again after HTML removal
            s = s.strip()
            # Truncate to 100 characters (column size limit)
            if len(s) > 100:
                s = s[:100]
            return s
        
        def safe_txn_id(val):
            if pd.isna(val) or val is None:
                return ''
            s = str(val).strip()
            if re.fullmatch(r'\d+\.0', s):
                s = s[:-2]
            if re.fullmatch(r'\d+(\.\d+)?e\+\d+', s, flags=re.IGNORECASE):
                try:
                    num = pd.to_numeric(val, errors='coerce')
                    if pd.notna(num):
                        s = f"{int(num):d}"
                except Exception:
                    pass
            return s

        def get_first_value(df, columns):
            """Return first non-empty value for given column names from df."""
            if df.empty:
                return None
            for col in columns:
                if col in df.columns:
                    val = df.iloc[0].get(col)
                    if pd.notna(val) and str(val).strip():
                        return str(val).strip()
            return None
        
        def norm(s):
            s = str(s).replace('\u00a0', ' ')
            s = re.sub(r'[\s/_\-\.]+', ' ', s).lower().strip()
            return s
        
        def get_txn_id_from_row(row, utr2_col=None):
            """Extract Transaction ID / UTR Number2 from a row."""
            # Try the detected column first (if provided)
            if utr2_col and utr2_col in row.index:
                val = row.get(utr2_col, '')
                s = safe_txn_id(val)
                if s:
                    return s
            
            # Try common column name variants (exact matches) - EXPANDED LIST
            variants = [
                'Transaction ID / UTR Number2',
                'Transaction Id / UTR Number2',
                'Transaction ID/ UTR Number2',
                'Transaction ID/UTR Number2',
                'Transaction ID / UTR Number 2',
                'Transaction Id / UTR Number 2',
                'Txn ID / UTR Number2',
                'Txn Id / UTR Number2',
                'UTR Number2',
                'Txn ID / UTR Number 2',
                'Txn Id / UTR Number 2',
                'Transaction ID/UTR Number 2',
                'Txn ID/UTR Number2',
                'Transaction ID / UTR',
                'Transaction ID/UTR',
                'Txn ID/UTR',
                'Transaction ID / UTR Number',
                'Txn ID / UTR Number',
                'UTR Number',
                'UTR',
            ]
            for col in variants:
                if col in row.index:
                    val = row.get(col, '')
                    s = safe_txn_id(val)
                    if s:
                        return s
            
            # Fuzzy matching: Look for columns containing UTR and Number 2 in normalized form
            def norm(s):
                s = str(s).replace('\u00a0', ' ')
                s = re.sub(r'[\s/_\-\.]+', ' ', s).lower().strip()
                return s
            
            for col in row.index:
                nc = norm(col)
                # Match columns that have UTR and (NUMBER 2 or ends with 2) and (TRANSACTION or TXN or ID)
                has_utr = 'utr' in nc
                has_number2 = ('number 2' in nc) or ('number2' in nc) or nc.endswith(' 2')
                has_txn_id = any(x in nc for x in ['transaction', 'txn', 'id'])
                
                if has_utr and has_number2 and has_txn_id:
                    val = row.get(col, '')
                    s = safe_txn_id(val)
                    if s:
                        return s
            
            # Last resort: Try any column with just "UTR" and "NUMBER"
            for col in row.index:
                nc = norm(col)
                if 'utr' in nc and 'number' in nc:
                    val = row.get(col, '')
                    s = safe_txn_id(val)
                    if s:
                        return s
            
            return ''
        
        def find_utr2_column(columns):
            """Find the 'Transaction ID / UTR Number2' column among various possible names."""
            # First, try exact matches
            exact_matches = [
                'Transaction ID / UTR Number2',
                'Transaction Id / UTR Number2',
                'Transaction ID/ UTR Number2',
                'Transaction ID/UTR Number2',
                'Transaction ID / UTR Number 2',
                'Transaction Id / UTR Number 2',
                'Txn ID / UTR Number2',
                'Txn Id / UTR Number2',
                'Txn ID / UTR Number 2',
                'Txn Id / UTR Number 2',
                'UTR Number2',
                'Txn ID/UTR Number2',
                'Transaction ID/UTR Number 2',
                'Transaction ID / UTR',
                'Transaction ID/UTR',
                'Txn ID/UTR',
                'Transaction ID / UTR Number',
            ]
            for col in columns:
                if col in exact_matches:
                    logger.debug(f"[FIND_UTR2] Exact match found: {col}")
                    return col
            
            # Then try fuzzy matching with normalized names
            def norm(s):
                s = str(s).replace('\u00a0', ' ')
                s = re.sub(r'[\s/_\-\.]+', ' ', s).lower().strip()
                return s
            
            known_normalized = [
                'transaction id utr number2',
                'transaction id utr number 2',
                'transaction id  utr number2',
                'transaction id  utr number 2',
                'transaction id number2',
                'transaction id utr',
                'txn id utr number2',
                'txn id utr number 2',
                'txn id utr',
                'utr number2',
                'utr number 2',
            ]
            
            normalized_map = {col: norm(col) for col in columns}
            for col, nc in normalized_map.items():
                if nc in known_normalized:
                    logger.debug(f"[FIND_UTR2] Normalized match found: '{col}' -> '{nc}'")
                    return col
            
            # Final fallback: Look for columns with all required components
            for col, nc in normalized_map.items():
                has_utr = 'utr' in nc
                has_number2 = ('number 2' in nc) or ('number2' in nc) or nc.endswith(' 2')
                has_txn_id = any(x in nc for x in ['transaction', 'txn', 'id'])
                
                if has_utr and has_number2 and has_txn_id:
                    logger.debug(f"[FIND_UTR2] Fuzzy pattern match found: '{col}' -> '{nc}'")
                    return col
            
            # Try ANY column with UTR in name
            for col, nc in normalized_map.items():
                if 'utr' in nc and 'number' in nc:
                    logger.debug(f"[FIND_UTR2] Fallback match (UTR + Number): '{col}' -> '{nc}'")
                    return col
            
            logger.debug(f"[FIND_UTR2] No match found. Available normalized columns: {list(normalized_map.values())}")
            return None

        utr2_col = find_utr2_column(tx_df.columns)
        logger.debug(f"[UPLOAD] Excel columns in 'Money Transfer to': {list(tx_df.columns)}")
        logger.debug(f"[UPLOAD] Detected UTR2 column: {utr2_col}")
        
        transactions = []

        txn_id_counts = {'found': 0, 'missing': 0}
        for idx, (_, row) in enumerate(tx_df.iterrows()):
            ack_no = str(row.get('Acknowledgement No.', '')).strip()
            if not ack_no:
                # ✅ Skip rows with missing ACK
                continue

            acc_to = str(row.get('Account No', '')).strip()
            extracted_txn_id = get_txn_id_from_row(row, utr2_col)
            atm_info = atm_df[atm_df['Account No./ (Wallet /PG/PA) Id'].astype(str).str.strip() == acc_to] if not atm_df.empty else pd.DataFrame()
            chq_info = chq_df[chq_df['Account No./ (Wallet /PG/PA) Id'].astype(str).str.strip() == acc_to] if not chq_df.empty else pd.DataFrame()
            hold_info = hold_df[(hold_df['Account No./ (Wallet /PG/PA) Id'].astype(str).str.strip() == acc_to) & (hold_df['Transaction Id / UTR Number'].astype(str).str.strip() == extracted_txn_id)] if not hold_df.empty and extracted_txn_id else pd.DataFrame()
            if extracted_txn_id:
                txn_id_counts['found'] += 1
                if idx < 2:  # Log first 2 rows with txn_id
                    logger.debug(f"[UPLOAD] Row {idx}: ACK={ack_no}, TXN_ID={extracted_txn_id}")
            else:
                txn_id_counts['missing'] += 1
                if idx < 2:  # Log first 2 rows without txn_id
                    logger.debug(f"[UPLOAD] Row {idx}: ACK={ack_no}, TXN_ID=EMPTY")
                    # Debug: log what's in the row related to UTR/Transaction
                    for col in row.index:
                        if 'utr' in col.lower() or 'transaction' in col.lower() or 'txn' in col.lower():
                            logger.debug(f"  -> {col}: [REDACTED]")
            
            # Validate before creating transaction
            from_account = str(row.get('Account No./ (Wallet /PG/PA) Id', '')).strip()
            to_account = acc_to  # Already stripped and extracted above
            raw_amount = row.get('Transaction Amount')
            cleaned_amount = clean_amount(raw_amount)

            if not validate_account_number(from_account):
                logger.warning(f"Invalid from_account: {from_account}")
                continue

            if not validate_account_number(to_account):
                logger.warning(f"Invalid to_account: {to_account}")
                continue

            if not validate_amount(cleaned_amount):
                logger.warning(f"Invalid amount: {cleaned_amount}")
                continue

            transaction = Transaction(
                layer=int(row.get('Layer', 0)),
                from_account=from_account,
                to_account=to_account,
                account_number=to_account,
                ack_no=ack_no,
                bank_name=clean_bank_name(row.get('Bank/FIs')),
                ifsc_code=str(row.get('Ifsc Code', '')).strip(),
                txn_date=str(row.get('Transaction Date', '')).strip(),
                txn_id=extracted_txn_id,
                amount=cleaned_amount,
                disputed_amount=clean_amount(row.get('Disputed Amount')),
                action_taken=str(row.get('Action Taken By bank', '')).strip(),
                atm_id=str(atm_info.iloc[0]['ATM ID']) if not atm_info.empty else None,
                atm_withdraw_amount=clean_amount(atm_info.iloc[0]['Withdrawal Amount']) if not atm_info.empty else None,
                atm_withdraw_date=str(atm_info.iloc[0]['Withdrawal Date & Time']) if not atm_info.empty else None,
                atm_location=clean_location(get_first_value(atm_info, [
                    'ATM Location',
                    'Location',
                    'ATM Location / City',
                    'ATM Address',
                    'ATM Location/City',
                    'Place/Location of ATM',
                    'Place / Location of ATM'
                ])),
                cheque_no=str(chq_info.iloc[0]['Cheque No']) if not chq_info.empty else None,
                cheque_withdraw_amount=clean_amount(chq_info.iloc[0]['Withdrawal Amount']) if not chq_info.empty else None,
                cheque_withdraw_date=str(chq_info.iloc[0]['Withdrawal Date & Time']) if not chq_info.empty else None,
                cheque_ifsc=str(chq_info.iloc[0]['Ifsc Code']) if not chq_info.empty else None,
                put_on_hold_txn_id=str(hold_info.iloc[0]['Transaction Id / UTR Number']) if not hold_info.empty else None,
                put_on_hold_date=str(hold_info.iloc[0]['Put on hold Date']) if not hold_info.empty else None,
                put_on_hold_amount=clean_amount(hold_info.iloc[0]['Put on hold Amount']) if not hold_info.empty else None,
                upload_id=uploaded_file.id
            )

            # Restore saved refund details if any (Persistent POH Data)
            if transaction.put_on_hold_txn_id:
                poh_details = POHRefundDetails.query.filter_by(
                    ack_no=transaction.ack_no, 
                    txn_id=transaction.put_on_hold_txn_id
                ).first()
                if poh_details:
                    transaction.court_order_date = poh_details.court_order_date
                    transaction.refund_status = poh_details.refund_status
                    transaction.refund_amount = poh_details.refund_amount

            # Collect transaction in list instead of adding directly
            transactions.append(transaction)

        # ✅ Sort transactions by layer in ascending order before inserting
        transactions.sort(key=lambda t: t.layer)

        # Add sorted transactions to the session
        for t in transactions:
            db.session.add(t)


        db.session.commit()
        logger.info(f"[UPLOAD] Txn ID extraction summary: Found={txn_id_counts['found']}, Missing={txn_id_counts['missing']}")
        flash("✅ Excel uploaded and data saved successfully.", "success")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to process Excel: {e}", exc_info=True)
        flash("Failed to process Excel file. Please check the file format and try again.", "danger")

    return redirect('/index')

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    # Sanitize filename
    safe_filename = secure_filename(filename)

    # Verify file exists in database (authorization check)
    uploaded_file = UploadedFile.query.filter_by(filename=safe_filename).first()
    if not uploaded_file:
        abort(404)

    # Construct safe path
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)

    # Verify path is within upload directory
    upload_dir = os.path.abspath(app.config['UPLOAD_FOLDER'])
    requested_path = os.path.abspath(file_path)

    if not requested_path.startswith(upload_dir):
        abort(403)

    # Verify file exists
    if not os.path.isfile(requested_path):
        abort(404)

    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_filename)

@app.route('/view_graph')
@login_required
def view_graph():
    ack_no = request.args.get('ack_no')
    check_case_access(ack_no)
    try:
        fname_row = db.session.query(UploadedFile.filename).join(Transaction, Transaction.upload_id == UploadedFile.id).filter(Transaction.ack_no == ack_no).order_by(UploadedFile.upload_time.desc()).first()
        fname = fname_row[0] if fname_row else None
        log_usage('view_graph', filename=fname, ack_no=ack_no)
    except Exception as e:
        logger.error(f"UsageLog view_graph error: {e}")
    return redirect(url_for('graph_tree1', ack_no=ack_no))

@app.route('/graph/<ack_no>')
@login_required
def graph_tree1(ack_no):
    check_case_access(ack_no)
    try:
        fname_row = db.session.query(UploadedFile.filename).join(Transaction, Transaction.upload_id == UploadedFile.id).filter(Transaction.ack_no == ack_no).order_by(UploadedFile.upload_time.desc()).first()
        fname = fname_row[0] if fname_row else None
        log_usage('graph_page', filename=fname, ack_no=ack_no)
    except Exception as e:
        logger.error(f"UsageLog graph_page error: {e}")

    # Calculate Layer 1 Total
    layer_1_total = 0.0
    formatted_l1_total = "0.00"
    try:
        l1_txns = Transaction.query.filter_by(ack_no=ack_no, layer=1).all()
        if l1_txns:
            layer_1_total = sum(t.amount for t in l1_txns if t.amount)
        
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

        formatted_l1_total = format_indian_currency(layer_1_total)
    except Exception as e:
        logger.error(f"Error calculating layer 1 total: {e}")

    return render_template('graph_tree1.html', ack_no=ack_no, role=session.get('role'), layer_1_total=formatted_l1_total)

@app.route('/complaints')
def complaints():
    if 'username' not in session:
        return redirect('/login')

    dummy_complaints = [
        {'ack_no': 'ACK123', 'victim_name': 'John Doe', 'date': '2024-12-10', 'status': 'Under Review'},
        {'ack_no': 'ACK456', 'victim_name': 'Jane Smith', 'date': '2024-12-11', 'status': 'Resolved'},
    ]
    return render_template('complaint.html', complaints=dummy_complaints)

@app.route('/graph_data/<ack_no>')
@login_required
def graph_data(ack_no):
    # Authorization check
    check_case_access(ack_no)

    try:
        ack_no = ack_no.strip()
        logger.info(f"Fetching graph data for ACK: {ack_no}")
        transactions = Transaction.query.filter_by(ack_no=ack_no).all()
        logger.info(f"Found {len(transactions)} transactions for ACK {ack_no}")

        # ✅ Restore POH Refund Details from persistent store (POHRefundDetails)
        # This ensures that even if the Transaction table is stale or reset, the refund details are preserved and displayed.
        try:
            poh_details_list = POHRefundDetails.query.filter_by(ack_no=ack_no).all()
            if poh_details_list:
                poh_map = {p.txn_id: p for p in poh_details_list}
                updated_count = 0
                for t in transactions:
                    if t.put_on_hold_txn_id and t.put_on_hold_txn_id in poh_map:
                        pdata = poh_map[t.put_on_hold_txn_id]
                        # Update in-memory object attributes for graph generation
                        t.court_order_date = pdata.court_order_date
                        t.refund_status = pdata.refund_status
                        t.refund_amount = pdata.refund_amount
                        updated_count += 1
                logger.info(f"Restored persistent POH details for {updated_count} transactions")
        except Exception as e:
            logger.error(f"Error restoring POH details in graph_data: {e}")

        # ✅ Restore KYC Details from persistent store (KYCDetails)
        try:
            txn_ids = [t.txn_id for t in transactions if t.txn_id]
            if txn_ids:
                # SQLite has limit on variables in IN clause, but usually 999. If txn count is high, might need chunking.
                # For now assuming manageable chunk or SQLAlchemy handles it (it often doesn't automatically chunk large lists).
                # To be safe, let's just query what we can. If it fails, we catch exception.
                kyc_list = KYCDetails.query.filter(KYCDetails.txn_id.in_(txn_ids)).all()
                kyc_map = {k.txn_id: k for k in kyc_list}
                
                kyc_updated_count = 0
                for t in transactions:
                    if t.txn_id and t.txn_id in kyc_map:
                        kdata = kyc_map[t.txn_id]
                        t.kyc_name = kdata.name
                        t.kyc_aadhar = kdata.aadhar
                        t.kyc_mobile = kdata.mobile
                        t.kyc_address = kdata.address
                        kyc_updated_count += 1
                logger.info(f"Restored persistent KYC details for {kyc_updated_count} transactions")
        except Exception as e:
            logger.error(f"Error restoring KYC details in graph_data: {e}")

        if not transactions:
            logger.warning(f"No transactions found for ACK {ack_no}")
            return jsonify({'error': 'No transactions found for this Acknowledgement No.'})


        

        def norm(s):
            s = str(s).replace('\u00a0', ' ')
            s = re.sub(r'[\s/_\-\.]+', ' ', s).lower().strip()
            return s
        
        def safe_txn_id(val):
            if pd.isna(val) or val is None:
                return ''
            s = str(val).strip()
            if re.fullmatch(r'\d+\.0', s):
                s = s[:-2]
            if re.fullmatch(r'\d+(\.\d+)?e\+\d+', s, flags=re.IGNORECASE):
                try:
                    num = pd.to_numeric(val, errors='coerce')
                    if pd.notna(num):
                        s = f"{int(num):d}"
                except Exception:
                    pass
            return s
        
        def find_utr2_column(columns):
            """Find the 'Transaction ID / UTR Number2' column among various possible names."""
            # First, try exact matches
            exact_matches = [
                'Transaction ID / UTR Number2',
                'Transaction Id / UTR Number2',
                'Transaction ID/ UTR Number2',
                'Transaction ID/UTR Number2',
                'Transaction ID / UTR Number 2',
                'Transaction Id / UTR Number 2',
                'Txn ID / UTR Number2',
                'Txn Id / UTR Number2',
                'Txn ID / UTR Number 2',
                'Txn Id / UTR Number 2',
                'UTR Number2',
                'Txn ID/UTR Number2',
                'Transaction ID/UTR Number 2',
                'Transaction ID / UTR',
                'Transaction ID/UTR',
                'Txn ID/UTR',
                'Transaction ID / UTR Number',
            ]
            for col in columns:
                if col in exact_matches:
                    return col
            
            # Then try fuzzy matching with normalized names
            known_normalized = [
                'transaction id utr number2',
                'transaction id utr number 2',
                'transaction id  utr number2',
                'transaction id  utr number 2',
                'transaction id number2',
                'transaction id utr',
                'txn id utr number2',
                'txn id utr number 2',
                'txn id utr',
                'utr number2',
                'utr number 2',
            ]
            
            normalized_map = {col: norm(col) for col in columns}
            for col, nc in normalized_map.items():
                if nc in known_normalized:
                    return col
            
            # Final fallback: Look for columns with all required components
            for col, nc in normalized_map.items():
                has_utr = 'utr' in nc
                has_number2 = ('number 2' in nc) or ('number2' in nc) or nc.endswith(' 2')
                has_txn_id = any(x in nc for x in ['transaction', 'txn', 'id'])
                
                if has_utr and has_number2 and has_txn_id:
                    return col
            
            # Try ANY column with UTR in name
            for col, nc in normalized_map.items():
                if 'utr' in nc and 'number' in nc:
                    return col
            
            return None
        
        def get_txn_id_from_df_row(row, utr2_col):
            """Extract Transaction ID / UTR Number2 from a dataframe row."""
            # Try the detected column first (if provided)
            if utr2_col and utr2_col in row.index:
                s = safe_txn_id(row.get(utr2_col, ''))
                if s:
                    return s
            
            # Try common column name variants (exact matches) - EXPANDED
            variants = [
                'Transaction ID / UTR Number2',
                'Transaction Id / UTR Number2',
                'Transaction ID/ UTR Number2',
                'Transaction ID/UTR Number2',
                'Transaction ID / UTR Number 2',
                'Transaction Id / UTR Number 2',
                'Txn ID / UTR Number2',
                'Txn Id / UTR Number2',
                'Txn ID / UTR Number 2',
                'Txn Id / UTR Number 2',
                'UTR Number2',
                'Transaction ID/UTR Number 2',
                'Txn ID/UTR Number2',
                'Transaction ID / UTR',
                'Transaction ID/UTR',
                'Txn ID/UTR',
                'Transaction ID / UTR Number',
                'Txn ID / UTR Number',
                'UTR Number',
                'UTR',
            ]
            for col in variants:
                if col in row.index:
                    s = safe_txn_id(row.get(col, ''))
                    if s:
                        return s
            
            # Fuzzy matching: Look for columns containing UTR and Number 2
            for col in row.index:
                nc = norm(col)
                has_utr = 'utr' in nc
                has_number2 = ('number 2' in nc) or ('number2' in nc) or nc.endswith(' 2')
                has_txn_id = any(x in nc for x in ['transaction', 'txn', 'id'])
                
                if has_utr and has_number2 and has_txn_id:
                    s = safe_txn_id(row.get(col, ''))
                    if s:
                        return s
            
            # Last resort: Try any column with just "UTR" and "NUMBER"
            for col in row.index:
                nc = norm(col)
                if 'utr' in nc and 'number' in nc:
                    s = safe_txn_id(row.get(col, ''))
                    if s:
                        return s
            
            return ''
        
        def clean_amt(v):
            if pd.isna(v) or v is None or v == '':
                return None
            try:
                s = str(v)
                s = re.sub(r'[^\d\.\-]', '', s)
                return float(s) if s else None
            except Exception:
                return None

        # OPTIMIZATION: Disabled on-the-fly Excel parsing to fix missing txn_ids.
        # This operation is extremely heavy (loads Excel file from DB) and should not be done on every read.
        # If txn_ids are missing, they should be fixed during upload or via a separate background process.
        """
        missing = [t for t in transactions if not (t.txn_id and str(t.txn_id).strip())]
        if missing:
            by_upload = {}
            for t in missing:
                if t.upload_id:
                    by_upload.setdefault(t.upload_id, []).append(t)
            for upload_id, txns in by_upload.items():
                up = UploadedFile.query.get(upload_id)
                if not up or not up.data:
                    continue
                try:
                    xls = pd.ExcelFile(io.BytesIO(up.data))
                    if 'Money Transfer to' not in xls.sheet_names:
                        continue
                    df = pd.read_excel(xls, sheet_name='Money Transfer to')
                    utr2_col = find_utr2_column(df.columns)
                    
                    # Log column info for debugging
                    logger.debug(f"Excel columns: {list(df.columns)}")
                    logger.debug(f"Detected UTR2 column: {utr2_col}")
                    
                    df_map = {}
                    df_rows = []
                    
                    # Build map and also store rows for fuzzy matching
                    for _, r in df.iterrows():
                        acc = str(r.get('Account No', '')).strip()
                        date = str(r.get('Transaction Date', '')).strip()
                        amt = clean_amt(r.get('Transaction Amount'))
                        txid = get_txn_id_from_df_row(r, utr2_col)
                        
                        if acc and date and amt is not None:
                            df_rows.append({
                                'acc': acc,
                                'date': date,
                                'amt': amt,
                                'txid': txid if txid else '',
                                'full_row': r
                            })
                            # Exact match key
                            if txid:
                                df_map[(acc, date, amt)] = txid
                    
                    logger.debug(f"Found {len(df_rows)} rows in Excel with txn data")
                    
                    # Try to match transactions
                    for t in txns:
                        key = (t.to_account or '', t.txn_date or '', float(t.amount) if t.amount is not None else None)
                        
                        # Try exact match first
                        if key in df_map:
                            t.txn_id = df_map[key]
                            logger.debug(f"Exact match found for [REDACTED]: {t.txn_id}")
                            continue
                        
                        # Try fuzzy matching: account + date match with amount tolerance
                        found = False
                        to_acc = t.to_account or ''
                        txn_date = t.txn_date or ''
                        txn_amt = float(t.amount) if t.amount is not None else None
                        
                        for excel_row in df_rows:
                            # Account and date must match exactly
                            if excel_row['acc'] == to_acc and excel_row['date'] == txn_date:
                                # Amount should be very close (within 0.01)
                                if txn_amt is not None and excel_row['amt'] is not None:
                                    if abs(txn_amt - excel_row['amt']) < 0.01 and excel_row['txid']:
                                        t.txn_id = excel_row['txid']
                                        logger.debug(f"Fuzzy match found for [REDACTED]: {t.txn_id}")
                                        found = True
                                        break
                                elif excel_row['txid']:
                                    # If amount is None, match anyway if we have a txid
                                    t.txn_id = excel_row['txid']
                                    logger.debug(f"Partial match found for [REDACTED]: {t.txn_id}")
                                    found = True
                                    break
                        
                        if not found and txns.index(t) < 3:  # Log first few unmatch to debug
                            logger.debug(f"No match found for txn: date={txn_date}, amt={txn_amt}")
                    
                    db.session.commit()
                    logger.info(f"Updated {len([t for t in txns if t.txn_id])} transactions with txn_id")
                except Exception as e:
                    logger.error(f"Error processing missing txn_ids: {e}", exc_info=True)
        """

        from_to_map = defaultdict(lambda: defaultdict(list))
        incoming_map = defaultdict(list)

        for t in transactions:
            key = (t.from_account, t.to_account, t.amount, t.txn_date, t.txn_id)
            if not any(txn['txn_id'] == t.txn_id for txn in from_to_map[t.from_account][t.to_account]):
                from_to_map[t.from_account][t.to_account].append({
                    'txn_id': t.txn_id,
                    'amount': t.amount,
                    'date': t.txn_date,
                    'ack_no': t.ack_no
                })
                incoming_map[t.to_account].append({
                    'from_account': t.from_account,
                    'amount': t.amount,
                    'date': t.txn_date,
                    'ack_no': t.ack_no,
                    'txn_id': t.txn_id,
                })

        from_layer_map = {t.from_account: t.layer for t in transactions if t.from_account}

        def build_hierarchy(rows):
            root = {'name': 'Flow', 'children': []}

            def find_node(n, target):
                if n['name'] == target:
                    return n
                for c in n.get('children', []):
                    found = find_node(c, target)
                    if found:
                        return found
                return None

            for t in rows:
                if t.layer == 1:
                    parent = next((c for c in root['children'] if c['name'] == t.from_account), None)
                    if not parent:
                        parent = {
                            'name': t.from_account,
                            'children': [],
                            'kyc_name': t.kyc_name,
                            'kyc_aadhar': t.kyc_aadhar,
                            'kyc_mobile': t.kyc_mobile,
                            'kyc_address': t.kyc_address,
                            'action': t.action_taken,
                        }
                        root['children'].append(parent)
                else:
                    parent = find_node(root, t.from_account)

                if parent:
                    existing = next((c for c in parent['children'] if c['name'] == t.to_account), None)
                    if not existing:
                        # ✅ calculate total amount of all transactions between parent → child
                        child = {
                            'name': t.to_account,
                            'children': [],
                            'layer': from_layer_map.get(t.to_account, t.layer),
                            'ack': t.ack_no,
                            'bank': t.bank_name,
                            'ifsc': t.ifsc_code,
                            'date': t.txn_date,
                            'txid': (
                                t.txn_id or next(
                                    (tx.get('txn_id') for tx in from_to_map[t.from_account][t.to_account] if tx.get('txn_id')),
                                    None
                                )
                            ),
                            'amt': str(t.amount),
                            'disputed': str(t.disputed_amount),
                            'action': t.action_taken,
                            'state': t.state if t.state and t.state != 'Unknown' else (t.ifsc_code or 'Unknown State'),
                            'atm_info': {
                                'atm_id': t.atm_id,
                                'amount': t.atm_withdraw_amount,
                                'date': t.atm_withdraw_date,
                                'location': t.atm_location
                            } if t.atm_id else None,
                            'cheque_info': {
                                'cheque_no': t.cheque_no,
                                'amount': t.cheque_withdraw_amount,
                                'date': t.cheque_withdraw_date,
                                'ifsc': t.cheque_ifsc
                            } if t.cheque_no else None,
                            'hold_info': {
                                'txn_id': t.put_on_hold_txn_id,
                                'amount': t.put_on_hold_amount,
                                'date': t.put_on_hold_date,
                                'court_order_date': t.court_order_date,
                                'refund_status': t.refund_status,
                                'refund_amount': t.refund_amount,
                            } if t.put_on_hold_txn_id else None,
                            'kyc_name': t.kyc_name,
                            'kyc_aadhar': t.kyc_aadhar,
                            'kyc_mobile': t.kyc_mobile,
                            'kyc_address': t.kyc_address,
                            # ✅ Keep all individual transactions for popup
                            'transactions_from_parent': from_to_map[t.from_account][t.to_account]
                        }
                        parent['children'].append(child)


            return root

        result = build_hierarchy(transactions)
        logger.info(f"Built hierarchy with {len(result['children'])} root children")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error processing graph data for ACK {ack_no}: {e}", exc_info=True)
        # Return a safe error message to the client while logging full traceback to server logs
        return jsonify({'error': 'Internal server error while processing graph data.'}), 500

@app.route('/available_ack_nos')
@login_required
def available_ack_nos():
    """List all available ACK numbers accessible to the current user"""
    if current_user.role in ['Admin']:
        # Admins and Viewers see all cases
        ack_nos = db.session.query(Transaction.ack_no).distinct().all()
    else:
        # Regular users only see cases assigned to them or uploaded by them
        complaints = Complaint.query.filter(
            or_(Complaint.assigned_to == current_user.id, Complaint.uploaded_by == current_user.id)
        ).with_entities(Complaint.ack_no).all()
        
        user_ack_nos = [c.ack_no for c in complaints]
        
        if not user_ack_nos:
            return jsonify({'available_ack_nos': []})

        # Only return ack_nos that actually have transactions and are authorized
        ack_nos = db.session.query(Transaction.ack_no).filter(
            Transaction.ack_no.in_(user_ack_nos)
        ).distinct().all()

    ack_list = [ack[0] for ack in ack_nos if ack[0]]
    return jsonify({'available_ack_nos': sorted(ack_list)})


@app.route('/atm_data/<ack_no>')
@login_required
def atm_data(ack_no):
    """Return rows from the ATM-related sheet for the uploaded Excel associated with this ack_no."""
    check_case_access(ack_no)
    try:
        # Find the most recent uploaded file for this ack_no
        up_row = db.session.query(UploadedFile).join(Transaction, Transaction.upload_id == UploadedFile.id).filter(Transaction.ack_no == ack_no).order_by(UploadedFile.upload_time.desc()).first()
        
        if not up_row:
             return jsonify({'atm': []})

        up = up_row
        file_bytes = None
        if up.data:
            file_bytes = up.data
        else:
            # Fallback: try to read the saved file from uploads folder
            # Ensure absolute path usage
            upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
            if not os.path.isabs(upload_folder):
                upload_folder = os.path.join(app.root_path, upload_folder)
            
            possible_path = os.path.join(upload_folder, up.filename) if up.filename else None
            
            if possible_path and os.path.exists(possible_path):
                try:
                    with open(possible_path, 'rb') as fh:
                        file_bytes = fh.read()
                except Exception as ex:
                    logger.warning(f"[atm_data] Failed to read file from disk: {ex}")
            else:
                logger.warning(f'[atm_data] File not found at {possible_path}')

        if not file_bytes:
            return jsonify({'atm': []})

        xls = pd.ExcelFile(io.BytesIO(file_bytes))

        # Robust sheet finding
        sheet_name = None
        # 1. Exact match candidates
        candidates = ['Withdrawal through ATM', 'Withdrawal through ATM ', 'Withdrawal through ATM\n']
        for c in candidates:
            if c in xls.sheet_names:
                sheet_name = c
                break
        
        # 2. Case-insensitive match
        if not sheet_name:
            lower_sheets = {s.lower().strip(): s for s in xls.sheet_names}
            if 'withdrawal through atm' in lower_sheets:
                sheet_name = lower_sheets['withdrawal through atm']

        # 3. Partial match
        if not sheet_name:
            for s in xls.sheet_names:
                if 'withdrawal' in s.lower() and 'atm' in s.lower():
                    sheet_name = s
                    break

        if not sheet_name:
            return jsonify({'atm': []})

        df = pd.read_excel(xls, sheet_name=sheet_name)
        
        # Filter by ACK Number if the column exists
        ack_col = None
        for col in df.columns:
            if 'acknowledgement' in str(col).lower() and 'no' in str(col).lower():
                ack_col = col
                break
        
        if ack_col:
            # Normalize ACK numbers for comparison
            df['ack_str'] = df[ack_col].astype(str).str.strip()
            # Filter logic can be added here if needed, currently returns all for the file
            pass

        df = df.fillna('')



        # Ensure columns are strings and replace non-ascii spacing
        def normalize_columns(cols):
            return [str(c).encode('ascii', 'ignore').decode().strip().replace('\u00A0', ' ').replace('\xa0', ' ') for c in cols]

        df.columns = normalize_columns(df.columns)
        logger.debug(f"[atm_data] Normalized columns: {list(df.columns)}")

        # Fetch layer mapping from Transactions for this ACK No
        layer_map = {}
        try:
            # Get distinct to_account -> layer mapping
            txns = db.session.query(Transaction.to_account, Transaction.layer)\
                .filter(Transaction.ack_no == ack_no)\
                .filter(Transaction.to_account.isnot(None))\
                .distinct().all()
            
            def normalize_db_acc(val):
                s = str(val).strip()
                # If it looks like a float ending in .0, strip it
                if s.endswith('.0'):
                    return s[:-2]
                return s

            for acc, lay in txns:
                if acc:
                    norm_acc = normalize_db_acc(acc)
                    layer_map[norm_acc] = lay
                    # Also store the original just in case
                    layer_map[str(acc).strip()] = lay
            
            logger.info(f"[atm_data] Built layer map for {len(layer_map)} accounts")
        except Exception as e:
            logger.error(f"[atm_data] Error building layer map: {e}")

        # Find Account Number column in the dataframe
        acc_col = None
        for col in df.columns:
            c_lower = col.lower()
            # Common patterns for account number column
            if 'account no' in c_lower or 'account number' in c_lower:
                acc_col = col
                break
        
        if acc_col:
            logger.info(f"[atm_data] Found account column: {acc_col}")
            def get_layer(row):
                val = row.get(acc_col)
                if pd.isna(val) or val == '':
                    return ''
                
                # Normalize the ATM account value
                s_val = str(val).strip()
                
                # 1. Try exact match
                if s_val in layer_map:
                    return layer_map[s_val]
                
                # 2. Try removing .0 suffix (common in pandas float->str)
                if s_val.endswith('.0') and s_val[:-2] in layer_map:
                    return layer_map[s_val[:-2]]
                
                # 3. Try converting scientific notation or float to int string
                try:
                    f_val = float(s_val)
                    int_val = str(int(f_val))
                    if int_val in layer_map:
                        return layer_map[int_val]
                except (ValueError, TypeError):
                    pass
                
                return ''

            df['Layer'] = df.apply(get_layer, axis=1)
        else:
            logger.warning("[atm_data] Could not find Account Number column in ATM sheet")
            df['Layer'] = ''

        rows = df.fillna('').to_dict(orient='records')
        logger.info(f"[atm_data] Rows extracted: {len(rows)}")
        return jsonify({'atm': rows, 'columns': list(df.columns)})
    except Exception as e:
        logger.error(f"[atm_data] Error: {e}", exc_info=True)
        return jsonify({'atm': [], 'error': str(e)})

@app.route('/statewise_summary/<ack_no>')
@login_required
def statewise_summary(ack_no):
    check_case_access(ack_no)
    try:
        # Check if we have any transactions with known states
        known_states_count = db.session.query(Transaction).filter(
            Transaction.ack_no == ack_no,
            Transaction.state.isnot(None),
            Transaction.state != 'Unknown'
        ).count()

        if known_states_count == 0:
            # If no known states, fetch synchronously for immediate response
            transactions_unknown = Transaction.query.filter(
                Transaction.ack_no == ack_no,
                (Transaction.state.is_(None) | (Transaction.state == 'Unknown')),
                Transaction.ifsc_code.isnot(None)
            ).all()

            if transactions_unknown:
                ifscs_to_fetch = {t.ifsc_code for t in transactions_unknown}
                ifsc_to_state = {}
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    future_to_ifsc = {executor.submit(get_state_from_api, ifsc): ifsc for ifsc in ifscs_to_fetch}
                    for future in concurrent.futures.as_completed(future_to_ifsc):
                        ifsc = future_to_ifsc[future]
                        try:
                            state = future.result()
                        except Exception as exc:
                            logger.error(f'IFSC {ifsc} generated an exception: {exc}')
                            state = 'Unknown'
                        ifsc_to_state[ifsc] = state

                # Save persistent cache
                save_ifsc_cache()

                # Update the database with the fetched states (normalized to title case)
                for t in transactions_unknown:
                    if t.ifsc_code in ifsc_to_state:
                        t.state = ifsc_to_state[t.ifsc_code].title()
                db.session.commit()

        # Now use database aggregation for efficiency
        from sqlalchemy import func, distinct

        state_summaries = db.session.query(
            Transaction.state,
            func.count(Transaction.id).label('total_transactions'),
            func.sum(Transaction.amount).label('total_amount'),
            func.group_concat(distinct(Transaction.ifsc_code)).label('ifsc_codes')
        ).filter(
            Transaction.ack_no == ack_no,
            Transaction.state.isnot(None),
            Transaction.state != 'Unknown'
        ).group_by(Transaction.state).all()

        # Define regions
        regions = {
            'Southern': ['Tamil Nadu', 'Kerala', 'Karnataka', 'Andhra Pradesh', 'Telangana', 'Puducherry', 'Lakshadweep', 'Andaman and Nicobar Islands'],
            'Western': ['Maharashtra', 'Gujarat', 'Rajasthan', 'Goa', 'Daman and Diu', 'Dadra and Nagar Haveli'],
            'Eastern': ['West Bengal', 'Odisha', 'Bihar', 'Jharkhand', 'Assam', 'Arunachal Pradesh', 'Nagaland', 'Manipur', 'Mizoram', 'Tripura', 'Meghalaya', 'Sikkim'],
            'Northern': ['Jammu and Kashmir', 'Himachal Pradesh', 'Punjab', 'Chandigarh', 'Uttarakhand', 'Haryana', 'Delhi', 'Uttar Pradesh', 'Madhya Pradesh', 'Chhattisgarh', 'Ladakh']
        }

        # Convert to list
        summaries = []
        for summary in state_summaries:
            state, total_transactions, total_amount, ifsc_codes_str = summary
            ifsc_codes = sorted(ifsc_codes_str.split(',')) if ifsc_codes_str else []
            formatted_state = state.title() if state and state != 'Unknown' else state
            summaries.append({
                'state': formatted_state,
                'total_transactions': total_transactions,
                'total_amount': float(total_amount) if total_amount else 0.0,
                'ifsc_codes': ifsc_codes
            })

        # Group by regions
        regional_summaries = {region: [] for region in regions}
        other_summaries = []
        for summary in summaries:
            state = summary['state']
            placed = False
            for region, states in regions.items():
                if state in states:
                    regional_summaries[region].append(summary)
                    placed = True
                    break
            if not placed:
                other_summaries.append(summary)

        # Sort within each region by total_amount descending, except Southern which uses custom order
        southern_order = ['Tamil Nadu', 'Kerala', 'Karnataka', 'Andhra Pradesh', 'Telangana', 'Puducherry', 'Lakshadweep', 'Andaman and Nicobar Islands']
        for region in regional_summaries:
            if region == 'Southern':
                # Sort Southern by custom order, then by amount descending for ties
                regional_summaries[region].sort(key=lambda x: (southern_order.index(x['state']) if x['state'] in southern_order else len(southern_order), -x['total_amount']))
            else:
                regional_summaries[region].sort(key=lambda x: x['total_amount'], reverse=True)

        # Concatenate in order: Southern, Western, Eastern, Northern, then others
        result = (regional_summaries['Southern'] +
                  regional_summaries['Western'] +
                  regional_summaries['Eastern'] +
                  regional_summaries['Northern'] +
                  other_summaries)

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in statewise_summary for {ack_no}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/put_on_hold_transactions/<ack_no>')
@login_required
def put_on_hold_transactions(ack_no):
    """Return all put-on-hold transactions for a complaint."""
    check_case_access(ack_no)
    try:
        from ifsc_utils import get_ifsc_info

        hold_txns = Transaction.query.filter(
            Transaction.ack_no == ack_no.strip(),
            Transaction.put_on_hold_txn_id.isnot(None)
        ).all()

        # ✅ Sync with persistent POH details
        poh_map = {}
        try:
            poh_details_list = POHRefundDetails.query.filter_by(ack_no=ack_no.strip()).all()
            poh_map = {p.txn_id: p for p in poh_details_list}
        except Exception as e:
            logger.error(f"Error fetching POH details in put_on_hold_transactions: {e}")

        response = []
        for t in hold_txns:
            # Fetch branch info on backend to avoid N+1 frontend calls
            ifsc_data = get_ifsc_info(t.ifsc_code) or {}
            branch_name = ifsc_data.get('BRANCH') or ifsc_data.get('Branch') or 'Unknown'

            # Get persistent details if available
            pdata = poh_map.get(t.put_on_hold_txn_id)
            court_date = pdata.court_order_date if pdata else t.court_order_date
            ref_status = pdata.refund_status if pdata else t.refund_status
            ref_amount = pdata.refund_amount if pdata else t.refund_amount

            response.append({
                'account_number': t.account_number or t.to_account,
                'bank_name': t.bank_name,
                'branch_name': branch_name,
                'ifsc_code': t.ifsc_code,
                'amount': t.put_on_hold_amount,
                'layer': t.layer,
                'court_order_date': court_date,
                'refund_status': ref_status,
                'refund_amount': ref_amount
            })

        return jsonify(response)
    except Exception as e:
        logger.error(f"Error fetching hold transactions for {ack_no}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/state_transactions/<ack_no>/<state>')
@login_required
def state_transactions(ack_no, state):
    check_case_access(ack_no)
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    offset = (page - 1) * per_page

    # Use case-insensitive and trimmed comparison for state matching
    state_lower = state.strip().lower()

    # Get total count for this specific state
    total_count = Transaction.query.filter(
        Transaction.ack_no == ack_no,
        db.func.lower(db.func.trim(Transaction.state)) == state_lower
    ).count()

    # Query transactions for this state with pagination, sorting ATM transactions first
    transactions = Transaction.query.filter(
        Transaction.ack_no == ack_no,
        db.func.lower(db.func.trim(Transaction.state)) == state_lower
    ).order_by(Transaction.atm_id.isnot(None).desc()).offset(offset).limit(per_page).all()

    state_transactions = []
    for t in transactions:
        # Case-insensitive comparison for state matching
        if t.state and t.state.lower() == state.lower():
            # Determine transaction type
            if t.atm_id is not None:
                txn_type = 'ATM Withdrawal'
                txn_amt = t.atm_withdraw_amount
                txn_id = 'N/A'
            elif t.cheque_no is not None:
                txn_type = 'Cheque Withdrawal'
                txn_amt = t.cheque_withdraw_amount
                txn_id = 'N/A'
            elif t.put_on_hold_txn_id is not None:
                txn_type = 'Put on Hold'
                txn_amt = t.put_on_hold_amount
                txn_id = 'N/A'
            else:
                txn_type = 'Account Transfer'
                txn_amt = str(t.amount)
                txn_id = t.txn_id

            state_transactions.append({
                'ack_no': t.ack_no,
                'account_name': t.account_number,
                'bank_name': t.bank_name,
                'amount': txn_amt,
                'ifsc_code': t.ifsc_code,
                'date': t.txn_date or 'N/A',
                'transaction_type': txn_type,
                #'status': t.action_taken or 'N/A',
                'transaction_id': txn_id,
                'layer' : t.layer or 'N/A', #added by D
                'is_atm': t.atm_id is not None
            })

    return jsonify({
        'transactions': state_transactions,
        'total_count': total_count,
        'page': page,
        'per_page': per_page,
        'total_pages': (total_count + per_page - 1) // per_page
    })

@app.route('/save_kyc', methods=['POST'])
def save_kyc():
    if session.get('role') in VIEW_ONLY_ROLES:
        return jsonify({"status": "error", "message": "View-only users cannot edit KYC"}), 403
    data = request.get_json()
    txn_id = data.get('txn_id')

    if not txn_id:
        return jsonify({"status": "error", "message": "Transaction ID missing"}), 400

    try:
        # Save to persistent KYC store
        kyc_entry = KYCDetails.query.filter_by(txn_id=txn_id).first()
        if not kyc_entry:
            kyc_entry = KYCDetails(txn_id=txn_id)
            db.session.add(kyc_entry)
        
        kyc_entry.name = data.get('name')
        kyc_entry.aadhar = data.get('aadhar')
        kyc_entry.mobile = data.get('mobile')
        kyc_entry.address = data.get('address')
        
        # Also update the main Transaction table for backward compatibility
        txn = Transaction.query.filter_by(txn_id=txn_id).first()
        if txn:
            txn.kyc_name = data.get('name')
            txn.kyc_aadhar = data.get('aadhar')
            txn.kyc_mobile = data.get('mobile')
            txn.kyc_address = data.get('address')

        db.session.commit()
        logger.info(f"KYC Save Request processed for txn_id: {txn_id}")
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error saving KYC: {e}")
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/save_hold_refund', methods=['POST'])
def save_hold_refund():
    """Save court order / refund details for a put-on-hold transaction."""
    try:
        if session.get('role') in VIEW_ONLY_ROLES:
            return jsonify({"status": "error", "message": "View-only users cannot edit refund details"}), 403

        data = request.get_json() or {}
        ack_no = (data.get('ack_no') or '').strip()
        hold_txn_id = (data.get('hold_txn_id') or '').strip()

        logger.info(f"save_hold_refund request: ack_no={ack_no}, hold_txn_id={hold_txn_id}, data={data}")

        if not ack_no or not hold_txn_id:
            logger.error("Missing required identifiers in save_hold_refund")
            return jsonify({"status": "error", "message": "Missing required identifiers"}), 400

        txn = Transaction.query.filter_by(
            ack_no=ack_no,
            put_on_hold_txn_id=hold_txn_id
        ).first()

        if not txn:
            logger.error(f"Put-on-hold transaction not found for ack={ack_no}, id={hold_txn_id}")
            return jsonify({"status": "error", "message": "Put-on-hold transaction not found"}), 404

        txn.court_order_date = (data.get('court_order_date') or '').strip() or None
        txn.refund_status = (data.get('refund_status') or '').strip() or None

        refund_amount_raw = data.get('refund_amount')
        try:
            txn.refund_amount = float(refund_amount_raw) if refund_amount_raw not in (None, '') else None
        except (TypeError, ValueError):
            logger.error(f"Invalid refund amount: {refund_amount_raw}")
            return jsonify({"status": "error", "message": "Invalid refund amount"}), 400

        # Update or Create POHRefundDetails for persistence
        poh_details = POHRefundDetails.query.filter_by(ack_no=ack_no, txn_id=hold_txn_id).first()
        if not poh_details:
            poh_details = POHRefundDetails(ack_no=ack_no, txn_id=hold_txn_id)
            db.session.add(poh_details)
        
        poh_details.court_order_date = txn.court_order_date
        poh_details.refund_status = txn.refund_status
        poh_details.refund_amount = txn.refund_amount

        db.session.commit()
        logger.info("Refund details saved successfully (persisted to POHRefundDetails)")

        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error in save_hold_refund: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


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

def get_layer_1_total(ack_no):
    try:
        # Assuming Transaction model and db session are available globally
        l1_txns = Transaction.query.filter_by(ack_no=ack_no, layer=1).all()
        return sum(t.amount for t in l1_txns if t.amount) if l1_txns else 0.0
    except Exception as e:
        logger.error(f"Error calculating layer 1 total: {e}")
        return 0.0

@app.route('/generate_letter', methods=['POST'])
def generate_letter():
    """Generate a letter (HTML) from a template and provided details.
    Expects JSON with keys: ack_no, account_number, letter_type ('suspect'|'victim'),
    and officer details: officer_name, officer_designation, officer_phone, officer_email,
    letter_date, crime_no, ncrp_ack_no
    Returns rendered HTML for client to open/print.
    """
    try:
        data = request.get_json() or {}
        ack_no = data.get('ack_no')
        account_number = data.get('account_number')
        letter_type = data.get('letter_type')

        # Collect officer/letter details with sensible defaults
        context = {
            'ack_no': ack_no,
            'account_number': account_number,
            'officer_name': data.get('officer_name', ''),
            'officer_designation': data.get('officer_designation', ''),
            'officer_phone': data.get('officer_phone', ''),
            'officer_email': data.get('officer_email', ''),
            'letter_date': data.get('letter_date', datetime.now().strftime('%d-%m-%Y')),
            'crime_no': data.get('crime_no', ''),
            'ncrp_ack_no': data.get('ncrp_ack_no', ack_no or ''),
            'layer_label': 'Unknown layer',
            'layer_1_total': format_indian_currency(get_layer_1_total(ack_no))
        }

        # Choose template
        if letter_type == 'victim':
            template_name = 'letter_victim.html'
        else:
            template_name = 'letter_suspect.html'

        # Log usage
        try:
            log_usage('generate_letter', filename=template_name, ack_no=ack_no)
        except Exception:
            pass

        return render_template(template_name, **context)
    except Exception as e:
        logger.error(f"Error generating letter: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/generate_letter_pdf', methods=['POST'])
def generate_letter_pdf():
    """Generate a letter (PDF) from a template and provided details.
    Saves the PDF in a folder named after the ACK no.
    """
    try:
        data = request.get_json() or {}
        ack_no = data.get('ack_no')
        account_number = data.get('account_number')
        letter_type = data.get('letter_type')

        # Collect officer/letter details with sensible defaults
        context = {
            'ack_no': ack_no,
            'account_number': account_number,
            'officer_name': data.get('officer_name', ''),
            'officer_designation': data.get('officer_designation', ''),
            'officer_phone': data.get('officer_phone', ''),
            'officer_email': data.get('officer_email', ''),
            'letter_date': data.get('letter_date', datetime.now().strftime('%d-%m-%Y')),
            'crime_no': data.get('crime_no', ''),
            'ncrp_ack_no': data.get('ncrp_ack_no', ack_no or ''),
            'layer_1_total': format_indian_currency(get_layer_1_total(ack_no))
        }

        # Choose template
        if letter_type == 'victim':
            template_name = 'letter_victim.html'
        else:
            template_name = 'letter_suspect.html'

        # Derive layer
        try:
            txns_for_layer = Transaction.query.filter(
                Transaction.ack_no == ack_no,
                or_(Transaction.to_account == account_number, Transaction.account_number == account_number)
            ).all()
            for t in txns_for_layer:
                if getattr(t, 'layer', None):
                    context['layer_label'] = f"{ordinal(t.layer)} layer"
                    break
        except Exception:
            pass

        # Render HTML
        html_content = render_template(template_name, **context)

        # Create PDF
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(
            io.BytesIO(html_content.encode('utf-8')),
            dest=pdf_buffer
        )

        if pisa_status.err:
            return jsonify({'error': 'PDF generation failed'}), 500

        # Create folder and save file
        folder_name = context['ncrp_ack_no'] or 'Unknown_ACK'
        # Clean folder name to be safe
        folder_name = secure_filename(folder_name)
        
        # Save in a 'generated_letters' directory to avoid cluttering root
        base_dir = os.path.join(app.root_path, 'generated_letters')
        target_dir = os.path.join(base_dir, folder_name)
        os.makedirs(target_dir, exist_ok=True)
        
        filename = f"{letter_type}_Letter_{account_number}.pdf"
        safe_filename_val = secure_filename(filename)
        file_path = os.path.join(target_dir, safe_filename_val)
        
        with open(file_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())

        # Reset buffer position for download
        pdf_buffer.seek(0)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=safe_filename_val
        )

    except Exception as e:
        logger.error(f"Error generating PDF letter: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/generate_letter_docx', methods=['POST'])
def generate_letter_docx():
    """Generate a letter (DOCX) from a template and provided details.
    Saves the DOCX in a folder named after the ACK no.
    """
    try:
        data = request.get_json() or {}
        ack_no = data.get('ack_no')
        
        # Support both single and multiple accounts
        account_numbers = data.get('account_numbers', [])
        l1_txns = Transaction.query.filter_by(ack_no=ack_no, layer=1).all()
        if not account_numbers and data.get('account_number'):
            account_numbers = [data.get('account_number')]
            
        if not account_numbers:
             return jsonify({'error': 'No account numbers provided'}), 400

        letter_type = data.get('letter_type')
        is_poh = data.get('is_poh', False)
        is_l1_grouped = data.get('is_l1_grouped', False)

        # Collect details
        context = {
            'ack_no': ack_no,
            'officer_name': data.get('officer_name', '<Name>'),
            'officer_designation': data.get('officer_designation', '<Rank>'),
            'officer_phone': data.get('officer_phone', '<Phone>'),
            'officer_email': data.get('officer_email', '<email id>'),
            'letter_date': data.get('letter_date', datetime.now().strftime('%d-%m-%Y')),
            'crime_no': data.get('crime_no', '<Cr.No>'),
            'ncrp_ack_no': data.get('ncrp_ack_no', ack_no or '<Acknowledgement no>')
        }
        
        # Calculate Layer 1 Total (Common for all letters in this ACK)
        layer_1_total = 0.0
        formatted_l1_total = "0.00"
        try:
            if l1_txns:
                layer_1_total = sum(t.amount for t in l1_txns if t.amount)
            
            # Helper for currency
            def format_indian_currency(amount):
                try:
                    amount = float(amount)
                except (ValueError, TypeError):
                    return "0.00"
                is_int = amount.is_integer()
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

            formatted_l1_total = format_indian_currency(layer_1_total)
        except Exception as e:
            logger.error(f"Error calculating layer 1 total: {e}")

        # Prepare ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            
            # If grouped, first fetch all Layer 1 txns and group them
            txns_groups = []
            all_txns = Transaction.query.filter_by(ack_no=ack_no).all()
            if is_l1_grouped:
                bmap = {}
                for t in l1_txns:
                    # Robust bank name normalization
                    bname = (t.bank_name or t.ifsc_code or "Unknown Bank").strip().upper()
                    if bname not in bmap:
                        bmap[bname] = []
                    bmap[bname].append(t)
                txns_groups = list(bmap.values())
                logger.info(f"Grouped {len(l1_txns)} Layer 1 transactions into {len(txns_groups)} bank groups.")
            elif is_poh:
                txn_map = {str(t.txn_id): t for t in all_txns if t.txn_id}

                for acc in account_numbers:
                    poh_txns = [
                        t for t in all_txns
                        if (
                            str(t.account_number or '') == str(acc)
                            or str(t.to_account or '') == str(acc)
                        )
                        and t.put_on_hold_txn_id
                    ]

                    seed_ids = {
                        str(t.put_on_hold_txn_id)
                        for t in poh_txns if t.put_on_hold_txn_id
                    }

                    if not seed_ids:
                        continue

                    expanded_ids = set(seed_ids)
                    queue = list(seed_ids)

                    while queue:
                        cur_id = queue.pop(0)
                        cur_txn = txn_map.get(str(cur_id))
                        if not cur_txn:
                            continue

                        # upstream
                        parent_acc = cur_txn.from_account
                        if parent_acc:
                            parents = [
                                t for t in all_txns
                                if (t.to_account == parent_acc or t.account_number == parent_acc) and t.txn_id
                            ]
                            for p in parents:
                                pid = str(p.txn_id)
                                if pid not in expanded_ids:
                                    expanded_ids.add(pid)
                                    queue.append(pid)

                    expanded_txns = [
                        t for t in all_txns if str(t.txn_id) in expanded_ids
                    ]

                    if expanded_txns:
                        grouped = {}
                        for t in expanded_txns:
                            key = t.to_account or t.account_number or t.from_account or "UNKNOWN"
                            grouped.setdefault(key, []).append(t)

                        for key, tx_list in grouped.items():
                            txns_groups.append({"transactions": tx_list,"folder": acc})
            # Helper to create and save a DOCX for a transactions list. Optionally place under a seed subfolder.
            def _save_doc_for_transactions(transactions, seed_folder=None):
                if not transactions:
                    return

                account_number_local = (transactions[0].to_account or transactions[0].account_number or transactions[0].from_account or "UNKNOWN")

                bank_name = "Unknown Bank"
                amount_lost = 0.0
                from_date_local = context['letter_date']

                for t in transactions:
                    if t.bank_name:
                        bank_name = t.bank_name
                        break
                    if t.ifsc_code:
                        bank_name = t.ifsc_code

                dates = []
                if is_poh:
                    amount_lost = sum(t.put_on_hold_amount for t in transactions if t.put_on_hold_amount)
                    dates = [t.put_on_hold_date for t in transactions if t.put_on_hold_date]
                else:
                    amount_lost = sum(t.amount for t in transactions if t.amount)
                    dates = [t.txn_date for t in transactions if t.txn_date]

                if dates:
                    try:
                        from_date_local = min(dates, key=lambda x: pd.to_datetime(x, dayfirst=True))
                    except Exception:
                        from_date_local = min(dates)

                suspect_layer = "Unknown"
                layer_label = "Unknown layer"
                date_minus_6_str = from_date_local

                for t in transactions:
                    if getattr(t, 'layer', None):
                        suspect_layer = str(t.layer)
                        layer_label = f"{ordinal(t.layer)} layer"
                        break
                try:
                    dt_obj = pd.to_datetime(from_date_local, dayfirst=True)
                    new_month = dt_obj.month - 6
                    new_year = dt_obj.year
                    if new_month <= 0:
                        new_month += 12
                        new_year -= 1
                    dt_minus_6 = dt_obj.replace(year=new_year, month=new_month, day=1)
                    date_minus_6_str = dt_minus_6.strftime('%d-%m-%Y')
                except Exception:
                    date_minus_6_str = from_date_local

                if letter_type == 'victim':
                    template_name_local = 'Template for letter generation_victim account.docx'
                else:
                    template_name_local = 'Template for letter generation_suspect accounts.docx'

                template_path_local = resource_path(template_name_local)
                if os.path.exists(template_path_local):
                    doc = Document(template_path_local)
                else:
                    doc = Document()
                    doc.add_paragraph("Template not found.")

                replacements = {
                    '<Bank Name>': bank_name,
                    '<amount lost>': f"{amount_lost:,.2f}",
                    '<total amount>': f"{amount_lost:,.2f}",
                    '(corresponding layer)': layer_label,
                    '<layer>': layer_label,
                    '<add all layer 1 amount>': formatted_l1_total,
                    'over all 1st layer total amount': formatted_l1_total,
                    'overall 1st layer total amount': formatted_l1_total,
                    '< Layer >': layer_label,
                    '<Layer>': layer_label,
                    '< layer >': layer_label,
                    '<transaction date - 6 months>': date_minus_6_str,
                    '<from date>': from_date_local,
                    '<Rank>': context['officer_designation'],
                    '<Name>': context['officer_name'],
                    '<Phno>': context['officer_phone'],
                    '<email id>': context['officer_email'],
                    '<Cr.No>': context['crime_no'],
                    '<Acknowledgement no>': context['ncrp_ack_no'],
                    '<Account No>': account_number_local,
                    '<To Date>': context['letter_date'],
                    '<current date>': context['letter_date'],
                    '<Suspect Account Number>': str(account_number_local),
                    '<Suspect account number>': str(account_number_local),
                    '<suspect account number>': str(account_number_local),
                    '<Suspect Account>': str(account_number_local),
                }

                def replace_in_paragraph(paragraph):
                    for key, val in replacements.items():
                        if key in paragraph.text:
                            for run in paragraph.runs:
                                if key in run.text:
                                    run.text = run.text.replace(key, str(val))
                    for key, val in replacements.items():
                        if key in paragraph.text:
                            paragraph.text = paragraph.text.replace(key, str(val))

                for paragraph in doc.paragraphs:
                    replace_in_paragraph(paragraph)
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            for paragraph in cell.paragraphs:
                                replace_in_paragraph(paragraph)

                target_text_start = "I am the investigating officer"
                new_paragraph_text = f"I am the investigating officer of the case mentioned in the subject. In this case, the victim has lost {formatted_l1_total}. Of the amount lost, partial amounts has been sent to the account mentioned below. Request you to provide the required details to proceed with the further investigation."
                for p in doc.paragraphs:
                    if p.text.strip().startswith(target_text_start):
                        p.clear()
                        run = p.add_run(new_paragraph_text)
                        run.font.name = 'Bookman Old Style'
                        run.font.size = Pt(12)
                        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                        break

                try:
                    heading_text = "Suspect Account Txn Details"
                    for p in doc.paragraphs:
                        t = (p.text or "")
                        if heading_text in t:
                            p.text = f"({layer_label}) {heading_text}"
                            break
                except Exception:
                    pass

                target_table = None
                for table in doc.tables:
                    if len(table.rows) > 0:
                        header_cells = table.rows[0].cells
                        headers_text = [c.text.strip() for c in header_cells]
                        if "Suspect Account Number" in headers_text or "Transaction Id / UTR Number" in headers_text or "Victim Account Number" in headers_text:
                            target_table = table
                            break

                if target_table:
                    tr = target_table.rows[0]._tr
                    trPr = tr.get_or_add_trPr()
                    tblHeader = OxmlElement('w:tblHeader')
                    trPr.append(tblHeader)
                    for i in range(len(target_table.rows) - 1, 0, -1):
                        row = target_table.rows[i]
                        tbl = row._element
                        tbl.getparent().remove(tbl)
                else:
                    logger.warning("Transaction table not found in template, searching for insertion point.")
                    target_idx = -1
                    headings_to_find = ["Suspect Account Txn Details", "Suspect Account Number", "Suspect Account Details"]
                    for i, p in enumerate(doc.paragraphs):
                        p_text = p.text.strip()
                        if any(h in p_text for h in headings_to_find):
                            target_idx = i
                            break
                    if target_idx != -1:
                        target_table = doc.add_table(rows=1, cols=6)
                        target_table.style = 'Table Grid'
                        tr = target_table.rows[0]._tr
                        trPr = tr.get_or_add_trPr()
                        tblHeader = OxmlElement('w:tblHeader')
                        trPr.append(tblHeader)
                        hdr_cells = target_table.rows[0].cells
                        headers = ["S. No.", "Suspect Account Number", "Transaction Date", "Transaction Amount", "Transaction Id / UTR Number", "IFSC Code"]
                        for i, h in enumerate(headers):
                            hdr_cells[i].text = h
                            for p in hdr_cells[i].paragraphs:
                                for r in p.runs:
                                    r.bold = True
                        tbl, p = target_table._tbl, doc.paragraphs[target_idx]._p
                        p.addnext(tbl)

                if target_table:
                    for idx, t in enumerate(transactions, 1):
                        row = target_table.add_row().cells
                        row[0].text = str(idx)
                        if is_poh:
                            row[1].text = str(t.account_number or t.to_account or '')
                            row[2].text = str(t.put_on_hold_date or '')
                            row[3].text = str(t.put_on_hold_amount or '')
                            row[4].text = str(t.put_on_hold_txn_id or '')
                            row[5].text = str(t.ifsc_code or '')
                        else:
                            row[1].text = str(t.to_account or t.account_number or t.from_account or '')
                            row[2].text = str(t.txn_date or '')
                            row[3].text = str(t.amount or '')
                            row[4].text = str(t.txn_id or '')
                            row[5].text = str(t.ifsc_code or '')

                folder_name_local = context['ncrp_ack_no'] or 'Unknown_ACK'
                folder_name_local = secure_filename(folder_name_local)
                base_dir_local = os.path.join(app.root_path, 'generated_letters')
                ack_dir_local = os.path.join(base_dir_local, folder_name_local)

                if is_poh or letter_type == 'suspect':
                    subfolder_local = 'suspect letter'
                elif letter_type == 'victim':
                    subfolder_local = 'victim letter'
                else:
                    subfolder_local = 'other letters'

                # If seed_folder provided, place files directly under a folder named after the seed
                # i.e. generated_letters/<ACK>/<SEED_FOLDER>/<files>
                if seed_folder:
                    target_dir_local = os.path.join(ack_dir_local, secure_filename(seed_folder))
                    arc_subfolder = secure_filename(seed_folder)
                else:
                    target_dir_local = os.path.join(ack_dir_local, subfolder_local)
                    arc_subfolder = subfolder_local

                os.makedirs(target_dir_local, exist_ok=True)

                prefix_local = "Suspect_Account_Letter" if is_poh else letter_type + "_Letter"
                if is_l1_grouped:
                    safe_bank = secure_filename(bank_name) or "Grouped"
                    filename_local = f"{prefix_local}_L1_{safe_bank}_{secrets.token_hex(4)}.docx"
                else:
                    filename_local = f"{prefix_local}_{account_number_local}.docx"

                safe_filename_val_local = secure_filename(filename_local)
                file_path_local = os.path.join(target_dir_local, safe_filename_val_local)
                doc.save(file_path_local)

                arcname_local = os.path.join(arc_subfolder, safe_filename_val_local)
                zf.write(file_path_local, arcname=arcname_local)
            for item in txns_groups:
                if isinstance(item, dict):
                    _save_doc_for_transactions(
                        item["transactions"],
                        seed_folder=item.get("folder")
                    )
                else:
                    _save_doc_for_transactions(item)
        
        zip_buffer.seek(0)
        
        zip_filename = f"Letters_{ack_no}.zip"
        if len(account_numbers) == 1:
             # Try to keep single file naming convention for download if possible, or just default to zip
             pass

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )

    except Exception as e:
        logger.error(f"Error generating DOCX letter: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/view_all_complaints')
@login_required
def view_all_complaints():
    try:
        log_usage('view_all_complaints')
    except Exception as e:
        logger.error(f"UsageLog view_all_complaints error: {e}")
    
    # OPTIMIZATION: Use defer to skip loading the large 'data' column
    complaints = UploadedFile.query.options(defer(UploadedFile.data)).order_by(UploadedFile.upload_time.desc()).all()

    # OPTIMIZATION: Query Transaction table directly for upload_id -> ack_no mapping
    # This avoids joining the heavy UploadedFile table and uses the index on upload_id
    upload_ack_rows = (
        db.session.query(Transaction.upload_id, Transaction.ack_no)
        .filter(Transaction.ack_no.isnot(None))
        .distinct()
        .all()
    )

    upload_id_to_acks = {}
    for uid, ack in upload_ack_rows:
        if not ack or not uid:
            continue
        upload_id_to_acks.setdefault(uid, set()).add(ack)

    # Convert upload_time to IST (UTC+5:30) and attach ACK numbers by upload_id
    for c in complaints:
        if c.upload_time:
            c.upload_time = c.upload_time.replace(tzinfo=timezone.utc).astimezone(
                timezone(timedelta(hours=5, minutes=30))
            )

        ack_set = upload_id_to_acks.get(c.id, set())
        c.ack_nos = sorted(list(ack_set)) if ack_set else []
        # logger.debug(f"File: {c.filename}, ID: {c.id}, ACK numbers: {c.ack_nos}")

    # Deduplicate by ACK number (keep the latest upload per ACK based on ordering)
    seen_acks = set()
    unique_complaints = []
    for c in complaints:
        ack_value = c.ack_nos[0] if c.ack_nos else None
        if ack_value and ack_value in seen_acks:
            continue
        if ack_value:
            seen_acks.add(ack_value)
        unique_complaints.append(c)

    return render_template("view_all_complaints.html", complaint_data=unique_complaints)


@app.route('/view_officers')
def view_officers():
    if 'username' not in session or session.get('role') != 'Admin':
        return redirect('/login')

    # Get all officers
    officers = User.query.filter_by(role='Investigative Officer').all()

    # For each officer, count uploaded files
    officer_data = []
    for officer in officers:
        computed_upload_count = UploadedFile.query.filter_by(uploader=officer.username).count()
        upload_count = officer.manual_upload_count if officer.manual_upload_count is not None else computed_upload_count
        officer_data.append({
            'username': officer.username,
            'role': officer.role,
            'upload_count': upload_count,
            'computed_upload_count': computed_upload_count,
            'manual_upload_count': officer.manual_upload_count,
            'name': officer.name,
            'rank': officer.rank,
            'email': officer.email
        })

    return render_template('view_officers.html', officers=officer_data)

@app.route('/update_officer', methods=['POST'])
def update_officer():
    if 'username' not in session or session.get('role') != 'Admin':
        flash('Access Denied!')
        return redirect(url_for('login'))

    username = (request.form.get('username') or '').strip()
    if not username:
        flash('Invalid request.')
        return redirect(url_for('view_officers'))

    user = User.query.filter_by(username=username).first()
    if not user:
        flash('Officer not found.')
        return redirect(url_for('view_officers'))

    # Only allow editing investigative officers via this view
    if user.role != 'Investigative Officer':
        flash('Only Investigative Officers can be edited here.')
        return redirect(url_for('view_officers'))

    # Update editable fields (keep it minimal)
    user.name = (request.form.get('name') or '').strip() or None
    user.rank = (request.form.get('rank') or '').strip() or None
    user.email = (request.form.get('email') or '').strip() or None

    manual_upload_count_raw = (request.form.get('manual_upload_count') or '').strip()
    if manual_upload_count_raw == '':
        user.manual_upload_count = None
    else:
        try:
            user.manual_upload_count = int(manual_upload_count_raw)
        except ValueError:
            flash('No. of Files Uploaded must be a number (or leave blank).')
            return redirect(url_for('view_officers'))

    db.session.commit()
    flash(f'Officer {username} updated successfully.')
    return redirect(url_for('view_officers'))


@app.route('/edit_officer/<int:officer_id>', methods=['POST'])
@login_required
def edit_officer(officer_id):
    if session.get('role') != 'Admin':
        return jsonify({'error': 'Access denied'}), 403

    officer = User.query.get(officer_id)
    if not officer:
        return jsonify({'error': 'Officer not found'}), 404

    password = request.json.get('password')
    if password:
        try:
            officer.set_password(password)
            db.session.commit()
            return jsonify({'message': 'Password updated successfully'})
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
    
    return jsonify({'error': 'No password provided'}), 400


@app.route('/delete_officer', methods=['POST'])
def delete_officer():
    if 'username' not in session or session.get('role') != 'Admin':
        flash('Access Denied!')
        return redirect(url_for('login'))

    username = request.form.get('username')
    if not username:
        flash('Invalid request.')
        return redirect(url_for('view_officers'))

    user = User.query.filter_by(username=username).first()
    if not user:
        flash('Officer not found.')
        return redirect(url_for('view_officers'))

    if user.role == 'Admin':
        flash('Cannot delete admin user.')
        return redirect(url_for('view_officers'))

    db.session.delete(user)
    db.session.commit()    
    flash(f'Officer {username} deleted successfully.')
    return redirect(url_for('view_officers'))


# ─────────────────────────────────────────────────────────────────
#  File Management — view / download / delete uploaded Excel files
# ─────────────────────────────────────────────────────────────────
@app.route('/manage_files')
@login_required
@admin_required
def manage_files():
    """List all uploaded Excel files with per-file stats."""
    try:
        log_usage('manage_files')
    except Exception:
        pass
    files = UploadedFile.query.options(defer(UploadedFile.data)).order_by(UploadedFile.upload_time.desc()).all()
    file_stats = []
    for f in files:
        txns = Transaction.query.filter_by(upload_id=f.id).all()
        ack_nos = list({t.ack_no for t in txns if t.ack_no})
        total_amt    = sum(t.amount          or 0 for t in txns)
        disputed_amt = sum(t.disputed_amount or 0 for t in txns)
        hold_count   = sum(1 for t in txns if t.put_on_hold_txn_id)
        hold_amt     = sum(t.put_on_hold_amount or 0 for t in txns if t.put_on_hold_txn_id)
        layers       = sorted({t.layer for t in txns if t.layer})
        file_stats.append({
            'id':           f.id,
            'filename':     f.filename,
            'uploader':     f.uploader or '—',
            'upload_time':  f.upload_time.strftime('%d %b %Y, %H:%M') if f.upload_time else '—',
            'txn_count':    len(txns),
            'ack_nos':      ack_nos,
            'total_amt':    total_amt,
            'disputed_amt': disputed_amt,
            'hold_count':   hold_count,
            'hold_amt':     hold_amt,
            'layers':       layers,
        })
    return render_template('manage_files.html', file_stats=file_stats)


@app.route('/delete_upload/<int:file_id>', methods=['POST'])
@login_required
@admin_required
def delete_upload(file_id):
    """Delete an uploaded file and all its transactions."""
    f = UploadedFile.query.get_or_404(file_id)
    fname = f.filename
    try:
        # Delete transactions linked to this upload
        Transaction.query.filter_by(upload_id=file_id).delete(synchronize_session='fetch')
        db.session.delete(f)
        db.session.commit()
        # Remove disk copy if it exists
        disk_path = os.path.join(app.config.get('UPLOAD_FOLDER', ''), fname)
        if os.path.exists(disk_path):
            os.remove(disk_path)
        flash(f'File "{fname}" and all its transactions deleted.', 'success')
        log_usage('delete_upload', filename=fname)
    except Exception as e:
        db.session.rollback()
        logger.error(f"delete_upload error for id={file_id}: {e}")
        flash(f'Error deleting file: {e}', 'danger')
    return redirect(url_for('manage_files'))


@app.route('/download_upload/<int:file_id>')
@login_required
@admin_required
def download_upload(file_id):
    """Stream the original Excel file back to the browser."""
    f = UploadedFile.query.get_or_404(file_id)
    if not f.data:
        flash('File data not found in database.', 'danger')
        return redirect(url_for('manage_files'))
    log_usage('download_upload', filename=f.filename)
    return send_file(
        io.BytesIO(f.data),
        mimetype=f.mimetype or 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f.filename
    )


@app.route('/view_analytics')
@login_required
@admin_required
def view_analytics():
    try:
        log_usage('view_analytics')
    except Exception as e:
        logger.error(f"UsageLog view_analytics error: {e}")

    # ── Summary KPIs ──────────────────────────────────────────────────
    total_files   = db.session.query(func.count(func.distinct(UploadedFile.filename))).scalar() or 0
    total_txns    = db.session.query(func.count(Transaction.id)).scalar() or 0
    total_amount  = float(db.session.query(func.sum(Transaction.amount)).scalar() or 0)
    disputed_amt  = float(db.session.query(func.sum(Transaction.disputed_amount)).scalar() or 0)
    hold_amt      = float(db.session.query(func.sum(Transaction.put_on_hold_amount)).scalar() or 0)
    hold_count    = db.session.query(func.count(Transaction.id)).filter(Transaction.put_on_hold_txn_id.isnot(None)).scalar() or 0
    unique_accts  = db.session.query(func.count(func.distinct(Transaction.to_account))).scalar() or 0
    unique_banks  = db.session.query(func.count(func.distinct(Transaction.bank_name))).scalar() or 0
    unique_states = db.session.query(func.count(func.distinct(Transaction.state))).filter(Transaction.state.isnot(None)).scalar() or 0
    max_layer     = db.session.query(func.max(Transaction.layer)).scalar() or 0
    active_officers = db.session.query(func.count(func.distinct(UploadedFile.uploader))).scalar() or 0

    # ── Per-file breakdown (all important numbers) ────────────────────
    files = UploadedFile.query.options(defer(UploadedFile.data)).order_by(UploadedFile.upload_time.desc()).all()
    file_rows = []
    for f in files:
        txns = Transaction.query.filter_by(upload_id=f.id).all()
        ack_nos   = list({t.ack_no for t in txns if t.ack_no})
        fa        = sum(t.amount or 0 for t in txns)
        fd        = sum(t.disputed_amount or 0 for t in txns)
        fh        = sum(t.put_on_hold_amount or 0 for t in txns)
        fhc       = sum(1 for t in txns if t.put_on_hold_txn_id)
        file_rows.append({
            'filename':    f.filename,
            'uploader':    f.uploader or '—',
            'upload_time': f.upload_time.strftime('%d %b %Y, %H:%M') if f.upload_time else '—',
            'txn_count':   len(txns),
            'ack_count':   len(ack_nos),
            'total_amt':   fa,
            'disputed_amt':fd,
            'hold_amt':    fh,
            'hold_count':  fhc,
        })

    # ── Layer-wise distribution ───────────────────────────────────────
    layer_dist = db.session.query(
        Transaction.layer,
        func.count(Transaction.id),
        func.sum(Transaction.amount)
    ).group_by(Transaction.layer).order_by(Transaction.layer).all()

    # ── Top banks by transaction volume ──────────────────────────────
    top_banks = db.session.query(
        Transaction.bank_name,
        func.count(Transaction.id).label('cnt'),
        func.sum(Transaction.amount).label('amt')
    ).filter(Transaction.bank_name.isnot(None))\
     .group_by(Transaction.bank_name)\
     .order_by(desc('cnt')).limit(10).all()

    # ── Top IFSC codes ────────────────────────────────────────────────
    top_ifsc = db.session.query(
        Transaction.ifsc_code,
        Transaction.bank_name,
        func.count(Transaction.id).label('cnt')
    ).filter(Transaction.ifsc_code.isnot(None))\
     .group_by(Transaction.ifsc_code, Transaction.bank_name)\
     .order_by(desc('cnt')).limit(10).all()

    # ── State-wise distribution ───────────────────────────────────────
    state_dist = db.session.query(
        Transaction.state,
        func.count(Transaction.id).label('cnt'),
        func.sum(Transaction.amount).label('amt')
    ).filter(Transaction.state.isnot(None))\
     .group_by(Transaction.state)\
     .order_by(desc('cnt')).limit(15).all()

    # ── Officer upload stats ──────────────────────────────────────────
    officer_stats = db.session.query(
        User.username,
        User.name,
        func.count(UploadedFile.id).label('uploads')
    ).join(UploadedFile, UploadedFile.uploader == User.username)\
     .filter(User.role == 'Investigative Officer')\
     .group_by(User.username, User.name)\
     .order_by(desc('uploads')).all()

    # ── ATM / Cheque withdrawal counts ───────────────────────────────
    atm_count    = db.session.query(func.count(Transaction.id)).filter(Transaction.atm_id.isnot(None)).scalar() or 0
    cheque_count = db.session.query(func.count(Transaction.id)).filter(Transaction.cheque_no.isnot(None)).scalar() or 0

    return render_template("view_analytics.html",
        # KPIs
        total_files=total_files,    total_txns=total_txns,
        total_amount=total_amount,  disputed_amt=disputed_amt,
        hold_amt=hold_amt,          hold_count=hold_count,
        unique_accts=unique_accts,  unique_banks=unique_banks,
        unique_states=unique_states,max_layer=max_layer,
        active_officers=active_officers,
        atm_count=atm_count,        cheque_count=cheque_count,
        # Tables
        file_rows=file_rows,
        layer_dist=layer_dist,
        top_banks=top_banks,
        top_ifsc=top_ifsc,
        state_dist=state_dist,
        officer_stats=officer_stats,
    )
@app.route('/download_logs')
def download_logs():
    if 'username' not in session:
        return redirect('/login')
    try:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        logs = UsageLog.query.filter(UsageLog.timestamp >= start_of_day, UsageLog.timestamp < end_of_day).order_by(UsageLog.timestamp.asc()).all()
        
        # PDF Generation
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=landscape(A4))
        width, height = landscape(A4)
        y = height - 50
        
        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(30, y, f"Usage Logs - {start_of_day.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime('%Y-%m-%d')}")
        y -= 30
        
        # Headers - Adjusted for Landscape (Width ~842)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(30, y, "Timestamp")      # Left aligned
        c.drawString(180, y, "User (Role)")   # ~150px space
        c.drawString(350, y, "Action")        # ~150px space
        c.drawString(500, y, "Details (File/Ack)") # Rest of the space (~310px)
        y -= 20
        c.line(30, y+15, 810, y+15) # Line spans full width
        
        c.setFont("Helvetica", 9)
        
        for l in logs:
            if y < 50:
                c.showPage()
                y = height - 50
                # Redraw headers on new page
                c.setFont("Helvetica-Bold", 10)
                c.drawString(30, y, "Timestamp")
                c.drawString(180, y, "User (Role)")
                c.drawString(350, y, "Action")
                c.drawString(500, y, "Details (File/Ack)")
                y -= 20
                c.line(30, y+15, 810, y+15)
                c.setFont("Helvetica", 9)

            ts_ist = l.timestamp.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30)))
            ts_str = ts_ist.strftime('%Y-%m-%d %H:%M:%S')
            u = l.username or ''
            r = l.role or ''
            a = l.action or ''
            f = l.filename or ''
            an = l.ack_no or ''
            
            details = f"{f} {an}".strip()
            # No truncation
            
            user_role = f"{u} ({r})"
            if len(user_role) > 35: user_role = user_role[:32] + "..."

            c.drawString(30, y, ts_str)
            c.drawString(180, y, user_role)
            c.drawString(350, y, a)
            c.drawString(500, y, details)
            
            y -= 15
            
        c.save()
        buf.seek(0)
        
        fname = f"usage_logs_{start_of_day.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime('%Y-%m-%d')}.pdf"
        log_usage('download_logs')
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=fname)
    except Exception as e:
        logger.error(f"Failed to generate logs PDF: {e}")
        return f"Failed to generate logs: {e}", 500

@app.route('/delete_complaint/<int:complaint_id>', methods=['DELETE'])
@login_required
def delete_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)

    # Authorization check: only admin can delete
    if current_user.role != 'Admin':
        abort(403, description="You don't have permission to delete this complaint")

    # Additional audit logging
    logger.info(f"User {current_user.username} deleted complaint {complaint_id}")

    db.session.delete(complaint)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/delete_by_ack', methods=['POST'])
@login_required
def delete_by_ack():
    if current_user.role != 'Admin':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('admin_dashboard'))
        
    ack_no = request.form.get('ack_no', '').strip()
    if not ack_no:
        flash("Please provide an Acknowledgement Number.", "warning")
        return redirect(url_for('admin_dashboard'))

    try:
        # Delete from Transaction table
        deleted_count = Transaction.query.filter_by(ack_no=ack_no).delete()
        
        # Also delete from Complaint table if it exists there
        complaint_deleted = Complaint.query.filter_by(ack_no=ack_no).delete()
        
        db.session.commit()
        
        if deleted_count > 0 or complaint_deleted > 0:
            flash(f"Successfully deleted records for ACK No: {ack_no}", "success")
            logger.info(f"User {current_user.username} deleted ACK {ack_no}. Txns: {deleted_count}, Complaints: {complaint_deleted}")
        else:
            flash(f"No records found for ACK No: {ack_no}", "warning")
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting ACK {ack_no}: {e}")
        flash("An error occurred while deleting the records.", "danger")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/view_complaint/<int:complaint_id>')
@login_required
def view_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)

    # Authorization check: only admin, viewer, assigned officer, or creator can view
    if (current_user.role not in ['Admin'] and 
        complaint.assigned_to != current_user.id and 
        complaint.uploaded_by != current_user.id):
        abort(403, description="You don't have permission to view this complaint")

    return render_template('complaint.html', complaint=complaint)

@app.route('/admin/add_officer', methods=['GET'])
@login_required
@admin_required
def add_officer():
    # This page only shows the form. Submitting it POSTs to /submit_officer, which
    # validates the input, creates the officer, and re-renders this page with an
    # inline error message if anything is wrong.
    return render_template('add_officer.html')

@app.route('/submit_officer', methods=['POST'])
@login_required
def submit_officer():
    if session.get('role') != 'Admin':
        flash('Access Denied!', 'danger')
        return redirect(url_for('login'))

    name = request.form.get('name', '').strip()
    rank = request.form.get('rank', '').strip()
    email = request.form.get('email', '').strip()
    username = request.form.get('username', '').strip()
    # Do NOT strip the password: it is stored exactly as typed and must match what
    # the officer enters at login (the login route does not strip it either).
    password = request.form.get('password', '')

    # On any problem, re-render the SAME form with a clear inline error and keep
    # what was already typed. (The old code redirected to '/add_officer' — a route
    # that does not exist; the real one is '/admin/add_officer' — so a weak password
    # produced a 404 instead of a helpful message.)
    def _reject(message):
        return render_template(
            'add_officer.html',
            error=message,
            form={'name': name, 'rank': rank, 'email': email, 'username': username},
        )

    if not (name and rank and email and username and password):
        return _reject("All fields are required.")

    if User.query.filter_by(username=username).first():
        return _reject(f"The username '{username}' is already taken. Please choose another.")

    new_officer = User(
        username=username,
        role='Investigative Officer',
        name=name,
        rank=rank,
        email=email
    )
    try:
        # set_password enforces the complexity policy and raises ValueError naming
        # the exact rule that failed (e.g. "Password must be at least 12 characters").
        new_officer.set_password(password)
    except ValueError as e:
        return _reject(str(e))

    # This password is TEMPORARY. Force the officer to set their own on first login:
    # must_change_password makes the login flow redirect them straight to /change_password.
    new_officer.must_change_password = True
    db.session.add(new_officer)
    db.session.commit()

    flash(f"Officer '{username}' added successfully. They must set a new password on first login.", "success")
    return redirect(url_for('view_officers'))


with app.app_context():
    db.create_all()

    from werkzeug.security import generate_password_hash

    # ✅ Indentation correctly inside app_context
    if User.query.count() == 0:
        # Generate random initial passwords that meet complexity requirements
        def generate_secure_password(length=16):
            alphabet = string.ascii_letters + string.digits + '!@#$%^&*(),.?":{}|<>'
            while True:
                password = ''.join(secrets.choice(alphabet) for i in range(length))
                if (any(c.islower() for c in password)
                        and any(c.isupper() for c in password)
                        and any(c.isdigit() for c in password)
                        and any(c in '!@#$%^&*(),.?":{}|<>' for c in password)):
                    return password

        admin_password = generate_secure_password()
        officer_password = generate_secure_password()

        admin = User(username='admin', role='Admin')
        admin.set_password(admin_password)
        admin.must_change_password = True
        
        officer = User(username='officer', role='Investigative Officer')
        officer.set_password(officer_password)
        officer.must_change_password = True

        db.session.add(admin)
        db.session.add(officer)
        db.session.commit()
        
        logger.info("Users initialized with secure random passwords.")

        # Save the generated passwords to a gitignored file as well as printing them.
        # The console message scrolls away the moment the app starts logging requests,
        # which is exactly why the admin password kept getting "lost" after a clone.
        try:
            creds_path = os.path.join(secure_base, 'INITIAL_CREDENTIALS.txt')
            with open(creds_path, 'w') as cf:
                cf.write(
                    "FundTrail initial login credentials (auto-generated)\n"
                    "Change these on first login, then delete this file.\n\n"
                    f"  admin    password: {admin_password}\n"
                    f"  officer  password: {officer_password}\n"
                )
            if _is_posix():
                os.chmod(creds_path, 0o600)
            print(f"[SETUP] Credentials also saved to: {creds_path}")
        except Exception as exc:
            logger.warning(f"Could not write INITIAL_CREDENTIALS.txt: {exc}")

        print(f"[SETUP] Initial admin password: {admin_password}")
        print(f"[SETUP] Initial officer password: {officer_password}")
        print("[SETUP] Change these passwords immediately!")


# Configure custom error handlers
@app.errorhandler(CSRFError)
def handle_csrf_error(error):
    # Flask-WTF normally returns a raw "400 Bad Request: The CSRF token is missing".
    # That's what users were seeing on the Change/Reset Password form when their
    # session had expired or cookies weren't being stored. Show a friendly page that
    # explains it and lets them try again.
    return render_template("errors/csrf.html"), 400


@app.errorhandler(404)
def not_found(error):
    return render_template("errors/404.html"), 404


@app.errorhandler(403)
def forbidden(error):
    return render_template("errors/403.html"), 403


@app.errorhandler(500)
def internal_error(error):
    logger.error("Internal server error", exc_info=True)
    return render_template("errors/500.html"), 500


@app.route('/download_fundtrail_pdf', methods=['POST'])
@login_required
def download_fundtrail_pdf():
    """
    Generate a PDF visualising the fund trail using reportlab.
    Receives JSON data containing the chain of nodes.
    """
    try:
        data = request.get_json() or {}
        ack_no = data.get('ack_no', 'Unknown')
        nodes = data.get('nodes', [])

        if not nodes:
            return jsonify({'error': 'No data provided'}), 400

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # ---------- neutral palette ----------
        NAVY   = colors.HexColor('#0a2e63')
        GOLD   = colors.HexColor('#f5b301')
        INK    = colors.HexColor('#0f172a')
        LABELC = colors.HexColor('#475569')
        MUTED  = colors.HexColor('#64748b')
        LINEC  = colors.HexColor('#e2e8f0')
        SHADOW = colors.HexColor('#e6ebf2')
        CARDBG = colors.HexColor('#f8fafc')
        HEADSUB = colors.HexColor('#c7d6f0')

        # ---------- MEANING colours (each colour carries meaning) ----------
        # Victim = orange, intermediate layers = cream, last / on-hold = red.
        V_BG = colors.HexColor('#F59E0B'); V_AC = colors.HexColor('#d97706'); V_TI = colors.HexColor('#7c2d12')
        M_BG = colors.HexColor('#fcfaf9'); M_AC = colors.HexColor('#94a3b8'); M_TI = colors.HexColor('#334155')
        H_BG = colors.HexColor('#F86262'); H_AC = colors.HexColor('#b91c1c'); H_TI = colors.HexColor('#7f1d1d')

        MARGIN = 50
        HEAD_H = 80
        BOX_W = 360
        x = (width - BOX_W) / 2.0
        PAD = 16
        LINE_H = 15
        LABEL_W = 104

        def _to_f(v):
            try:
                return float(v)
            except Exception:
                return None

        def fmt_money(v):
            n = _to_f(v)
            if n is None:
                return str(v)
            neg = n < 0; n = abs(n)
            ip, dec = ("%.2f" % n).split('.')
            if len(ip) > 3:
                ip = re.sub(r'(\d)(?=(\d\d)+$)', r'\1,', ip[:-3]) + ',' + ip[-3:]
            return ('-' if neg else '') + 'Rs. ' + ip + '.' + dec

        def wrap(text, font, size, maxw):
            out = []
            for raw in str(text).split('\n'):
                cur = ''
                for w in raw.split(' '):
                    t = (cur + ' ' + w).strip()
                    if not cur or c.stringWidth(t, font, size) <= maxw:
                        cur = t
                    else:
                        out.append(cur); cur = w
                out.append(cur)
            return out or ['']

        def draw_band():
            # deep-navy letterhead band with a gold underline
            c.setFillColor(NAVY); c.rect(0, height - HEAD_H, width, HEAD_H, fill=1, stroke=0)
            c.setFillColor(GOLD); c.rect(0, height - HEAD_H, width, 3, fill=1, stroke=0)
            c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 19)
            c.drawString(MARGIN, height - 42, "Fund Trail Analysis")
            c.setFillColor(HEADSUB); c.setFont("Helvetica", 9.5)
            c.drawString(MARGIN, height - 58, "Put-On-Hold Money Trail   |   Tamil Nadu Cyber Crime Wing")
            c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 9.5)
            c.drawRightString(width - MARGIN, height - 40, "Ack No: %s" % ack_no)
            c.setFillColor(HEADSUB); c.setFont("Helvetica", 8.5)
            c.drawRightString(width - MARGIN, height - 56, "Generated " + datetime.now().strftime("%d %b %Y, %H:%M"))

        def draw_footer():
            c.setStrokeColor(LINEC); c.setLineWidth(0.8)
            c.line(MARGIN, 42, width - MARGIN, 42)
            c.setFillColor(MUTED); c.setFont("Helvetica", 8)
            c.drawString(MARGIN, 30, "CONFIDENTIAL  -  For authorised investigation use only")
            c.drawRightString(width - MARGIN, 30, "Page %d" % c.getPageNumber())

        def draw_summary(y_top):
            # summary-of-findings stat row (forensic reports lead with the key numbers)
            accounts = len(nodes)
            disputed = max([_to_f(n.get('disputed_amount')) or 0 for n in nodes] or [0])
            hold = _to_f(nodes[-1].get('hold_amount')) or 0
            cards = [("On-Hold / Frozen", fmt_money(hold), H_AC),
                     ("Disputed Amount", fmt_money(disputed), V_AC),
                     ("Accounts Traced", str(accounts), NAVY)]
            gap = 12; ch = 52
            cw = (width - 2 * MARGIN - 2 * gap) / 3.0
            cx = MARGIN
            for label, value, accent in cards:
                c.setFillColor(SHADOW); c.roundRect(cx + 1.5, y_top - ch - 1.5, cw, ch, 9, fill=1, stroke=0)
                c.setFillColor(CARDBG); c.setStrokeColor(LINEC); c.setLineWidth(1)
                c.roundRect(cx, y_top - ch, cw, ch, 9, fill=1, stroke=1)
                c.setFillColor(accent); c.roundRect(cx, y_top - ch, 4, ch, 2, fill=1, stroke=0)
                fs = 14.0
                while fs > 8 and c.stringWidth(value, "Helvetica-Bold", fs) > cw - 24:
                    fs -= 0.5
                c.setFillColor(INK); c.setFont("Helvetica-Bold", fs)
                c.drawString(cx + 14, y_top - 26, value)
                c.setFillColor(MUTED); c.setFont("Helvetica", 7.5)
                c.drawString(cx + 14, y_top - 42, label.upper())
                cx += cw + gap
            return y_top - ch

        def draw_legend(y):
            items = [(V_BG, "Victim"), (M_BG, "Intermediate"), (H_BG, "On-Hold / Frozen")]
            lx = MARGIN
            for col, lab in items:
                c.setFillColor(col); c.setStrokeColor(LINEC); c.setLineWidth(0.8)
                c.roundRect(lx, y - 8, 11, 11, 2.5, fill=1, stroke=1)
                c.setFillColor(LABELC); c.setFont("Helvetica", 8.5)
                c.drawString(lx + 16, y - 6, lab)
                lx += 16 + c.stringWidth(lab, "Helvetica", 8.5) + 22

        def begin_page(first):
            draw_band(); draw_footer()
            yy = height - HEAD_H - 26
            if first:
                yy = draw_summary(yy)
                draw_legend(yy - 22)
                yy = yy - 46
            return yy

        y = begin_page(True)

        for i, node in enumerate(nodes):
            if i == 0:
                bg, accent, tcolor, badge = V_BG, V_AC, V_TI, "VICTIM ACCOUNT"
            elif i == len(nodes) - 1:
                bg, accent, tcolor, badge = H_BG, H_AC, H_TI, "ON HOLD"
            else:
                bg, accent, tcolor, badge = M_BG, M_AC, M_TI, "LAYER %d" % i

            rows = [("Account No", node.get('account_number', 'N/A')),
                    ("Bank", node.get('bank', 'Unknown Bank'))]
            if i != 0:
                rows += [("Branch", node.get('branch', 'Unknown')),
                         ("IFSC", node.get('ifsc', 'N/A')),
                         ("Txn ID", node.get('txn_id', 'N/A')),
                         ("Transacted", fmt_money(node.get('amount', '0'))),
                         ("Disputed", fmt_money(node.get('disputed_amount', '0')))]
            if i == len(nodes) - 1 and node.get('hold_amount'):
                rows += [("On-Hold Amt", fmt_money(node.get('hold_amount')))]

            value_maxw = BOX_W - PAD * 2 - LABEL_W
            disp = []
            for label, value in rows:
                wl = wrap(value, "Helvetica", 10, value_maxw)
                disp.append((label, wl[0]))
                for extra in wl[1:]:
                    disp.append((None, extra))

            box_h = PAD + 20 + 14 + len(disp) * LINE_H + PAD

            if y - box_h < 58:
                c.showPage(); y = begin_page(False)

            top = y
            # soft drop shadow
            c.setFillColor(SHADOW)
            c.roundRect(x + 2.5, top - box_h - 3.5, BOX_W, box_h, 14, fill=1, stroke=0)
            # card body
            c.setFillColor(bg); c.setStrokeColor(LINEC); c.setLineWidth(1.2)
            c.roundRect(x, top - box_h, BOX_W, box_h, 14, fill=1, stroke=1)
            # left accent rail
            c.setFillColor(accent)
            c.roundRect(x, top - box_h, 6, box_h, 3, fill=1, stroke=0)

            # header row: pill badge + node index
            by = top - PAD - 10
            pw = c.stringWidth(badge, "Helvetica-Bold", 8.5) + 18
            c.setFillColor(accent); c.roundRect(x + PAD + 4, by - 3, pw, 17, 8.5, fill=1, stroke=0)
            c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 8.5)
            c.drawString(x + PAD + 13, by + 1.5, badge)
            c.setFillColor(tcolor); c.setFont("Helvetica-Bold", 10)
            c.drawRightString(x + BOX_W - PAD, by + 1.5, "#%d" % i)
            # divider
            c.setStrokeColor(accent); c.setLineWidth(0.8)
            c.line(x + PAD, by - 12, x + BOX_W - PAD, by - 12)

            ry = by - 28
            for label, value in disp:
                if label is not None:
                    c.setFillColor(LABELC); c.setFont("Helvetica", 9)
                    c.drawString(x + PAD + 6, ry, label.upper())
                c.setFillColor(INK); c.setFont("Helvetica", 10)
                c.drawString(x + PAD + 6 + LABEL_W, ry, value)
                ry -= LINE_H

            # connector to next layer, labelled with the amount that moved (fund-flow)
            if i < len(nodes) - 1:
                ax = width / 2.0
                c.setStrokeColor(MUTED); c.setLineWidth(1.4)
                c.line(ax, top - box_h, ax, top - box_h - 30)
                amt = fmt_money(nodes[i + 1].get('amount', '0'))
                if amt and amt not in ('Rs. 0.00', '0'):
                    pw = c.stringWidth(amt, "Helvetica-Bold", 8) + 16
                    c.setFillColor(colors.white); c.setStrokeColor(LINEC); c.setLineWidth(0.8)
                    c.roundRect(ax - pw / 2.0, top - box_h - 22, pw, 14, 7, fill=1, stroke=1)
                    c.setFillColor(LABELC); c.setFont("Helvetica-Bold", 8)
                    c.drawCentredString(ax, top - box_h - 18, amt)
                ah = top - box_h - 30
                c.setStrokeColor(MUTED)
                c.line(ax, ah, ax - 4, ah + 6); c.line(ax, ah, ax + 4, ah + 6)
                y = top - box_h - 42
            else:
                y = top - box_h - 20

        c.save()
        buffer.seek(0)
        
        filename = f"FundTrail_{ack_no}.pdf"
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"Error generating fundtrail PDF: {e}")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────
#  Officer Analytics — shows only the current officer's own uploads
# ─────────────────────────────────────────────────────────────────
@app.route('/my_analytics')
@login_required
def my_analytics():
    """Analytics filtered to the logged-in officer's own uploads only."""
    me = session.get('username')
    try:
        log_usage('my_analytics')
    except Exception:
        pass

    my_files = UploadedFile.query.options(defer(UploadedFile.data)).filter_by(uploader=me).order_by(UploadedFile.upload_time.desc()).all()
    my_file_ids = [f.id for f in my_files]

    # All my transactions
    my_txns = Transaction.query.filter(Transaction.upload_id.in_(my_file_ids)).all() if my_file_ids else []

    # KPIs
    total_files   = len(my_files)
    total_txns    = len(my_txns)
    total_amount  = sum(t.amount or 0 for t in my_txns)
    disputed_amt  = sum(t.disputed_amount or 0 for t in my_txns)
    hold_amt      = sum(t.put_on_hold_amount or 0 for t in my_txns if t.put_on_hold_txn_id)
    hold_count    = sum(1 for t in my_txns if t.put_on_hold_txn_id)
    unique_accts  = len({t.to_account for t in my_txns if t.to_account})
    unique_banks  = len({t.bank_name  for t in my_txns if t.bank_name})
    max_layer     = max((t.layer for t in my_txns if t.layer), default=0)
    atm_count     = sum(1 for t in my_txns if t.atm_id)
    cheque_count  = sum(1 for t in my_txns if t.cheque_no)

    # Per-file breakdown
    file_rows = []
    for f in my_files:
        ftxns = [t for t in my_txns if t.upload_id == f.id]
        ack_nos    = list({t.ack_no for t in ftxns if t.ack_no})
        fa         = sum(t.amount or 0 for t in ftxns)
        fd         = sum(t.disputed_amount or 0 for t in ftxns)
        fh         = sum(t.put_on_hold_amount or 0 for t in ftxns if t.put_on_hold_txn_id)
        fhc        = sum(1 for t in ftxns if t.put_on_hold_txn_id)
        file_rows.append({
            'id':           f.id,
            'filename':     f.filename,
            'upload_time':  f.upload_time.strftime('%d %b %Y, %H:%M') if f.upload_time else '—',
            'txn_count':    len(ftxns),
            'ack_nos':      ack_nos,
            'total_amt':    fa,
            'disputed_amt': fd,
            'hold_count':   fhc,
            'hold_amt':     fh,
        })

    # Layer-wise
    from collections import defaultdict
    layer_map = defaultdict(lambda: {'txns': 0, 'amt': 0.0})
    for t in my_txns:
        if t.layer:
            layer_map[t.layer]['txns'] += 1
            layer_map[t.layer]['amt']  += (t.amount or 0)
    layer_dist = [(lyr, v['txns'], v['amt']) for lyr, v in sorted(layer_map.items())]

    # Top banks
    bank_map = defaultdict(lambda: {'cnt': 0, 'amt': 0.0})
    for t in my_txns:
        if t.bank_name:
            bank_map[t.bank_name]['cnt'] += 1
            bank_map[t.bank_name]['amt'] += (t.amount or 0)
    top_banks = sorted(bank_map.items(), key=lambda x: -x[1]['cnt'])[:10]
    top_banks = [(b, v['cnt'], v['amt']) for b, v in top_banks]

    # State-wise
    state_map = defaultdict(lambda: {'cnt': 0, 'amt': 0.0})
    for t in my_txns:
        if t.state:
            state_map[t.state]['cnt'] += 1
            state_map[t.state]['amt'] += (t.amount or 0)
    state_dist = sorted(state_map.items(), key=lambda x: -x[1]['cnt'])[:15]
    state_dist = [(s, v['cnt'], v['amt']) for s, v in state_dist]

    # Top IFSC
    ifsc_map = defaultdict(lambda: {'cnt': 0, 'bank': ''})
    for t in my_txns:
        if t.ifsc_code:
            ifsc_map[t.ifsc_code]['cnt'] += 1
            ifsc_map[t.ifsc_code]['bank'] = t.bank_name or ''
    top_ifsc = sorted(ifsc_map.items(), key=lambda x: -x[1]['cnt'])[:10]
    top_ifsc = [(i, v['bank'], v['cnt']) for i, v in top_ifsc]

    return render_template('my_analytics.html',
        me=me,
        total_files=total_files,    total_txns=total_txns,
        total_amount=total_amount,  disputed_amt=disputed_amt,
        hold_amt=hold_amt,          hold_count=hold_count,
        unique_accts=unique_accts,  unique_banks=unique_banks,
        max_layer=max_layer,        atm_count=atm_count,
        cheque_count=cheque_count,
        file_rows=file_rows,
        layer_dist=layer_dist,
        top_banks=top_banks,
        top_ifsc=top_ifsc,
        state_dist=state_dist,
    )


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        ensure_transaction_columns()
        ensure_user_columns()
        initialize_secure_users()

    # Use environment variable to control debug mode
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    # Port is configurable via the PORT env var so it can avoid conflicts — e.g.
    # macOS AirPlay Receiver (Control Center) occupies 5000 by default. Default 5000.
    port = int(os.environ.get('PORT', '5000'))
    app.run(debug=debug_mode, host='127.0.0.1', port=port)

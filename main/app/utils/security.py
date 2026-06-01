from flask import abort, request
from flask_login import current_user
from functools import wraps
import re
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

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

def is_safe_url(target):
    ALLOWED_HOSTS = {'localhost', '127.0.0.1', '0.0.0.0'}
    if not target:
        return False
    if target.startswith('/') and not target.startswith('//'):
        return True
    parsed = urlparse(target)
    return parsed.netloc in ALLOWED_HOSTS and parsed.scheme in ('http', 'https')

def check_case_access(ack_no):
    """
    Verifies if the current user has access to the case identified by ack_no.
    Aborts with 403 if unauthorized.
    """
    from ..models import Complaint, Transaction
    
    if not current_user.is_authenticated:
        abort(403)

    # Admin and Viewer can access all cases
    if current_user.role in ['Admin', 'Viewer']:
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

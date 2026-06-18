from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from flask_login import UserMixin
import hashlib
import re

db = SQLAlchemy()

# Password policy constants (single source of truth for the whole app).
PASSWORD_MIN_LENGTH = 12
PASSWORD_HISTORY_LIMIT = 5  # block reuse of the last N passwords

# Valid case workflow states (Feature: Case Status Workflow).
CASE_STATUSES = ("Open", "Under Investigation", "Closed")


def utc_now():
    """Timezone-aware UTC now — replaces the deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)


def validate_password(password):
    """Enforce password complexity"""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain lowercase letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain number")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValueError("Password must contain special character")
    return True


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    layer = db.Column(db.Integer)
    from_account = db.Column(db.String(100))
    to_account = db.Column(db.String(100))
    ack_no = db.Column(db.String(100))
    bank_name = db.Column(db.String(100))
    ifsc_code = db.Column(db.String(50))
    txn_date = db.Column(db.String(100))
    txn_id = db.Column(db.String(100))
    amount = db.Column(db.Float)
    disputed_amount = db.Column(db.Float)
    action_taken = db.Column(db.String(255))
    account_number = db.Column(db.String(50))
    state = db.Column(db.String(50))  # Cache state from IFSC

    # ATM withdrawal details
    atm_id = db.Column(db.String(100))
    atm_withdraw_amount = db.Column(db.Float)
    atm_withdraw_date = db.Column(db.String(100))
    atm_location = db.Column(db.String(200))

    # Cheque withdrawal details
    cheque_no = db.Column(db.String(100))
    cheque_withdraw_amount = db.Column(db.Float)
    cheque_withdraw_date = db.Column(db.String(100))
    cheque_ifsc = db.Column(db.String(50))

    put_on_hold_txn_id = db.Column(db.String(100))
    put_on_hold_date = db.Column(db.String(100))
    put_on_hold_amount = db.Column(db.Float)

    # Court / refund details for put-on-hold transactions
    court_order_date = db.Column(db.String(20))
    refund_status = db.Column(db.String(50))
    refund_amount = db.Column(db.Float)
    refund_type = db.Column(db.String(10))  # FULL / PARTIAL (mirrors MRMTracking step6)

    # KYC details captured against the transaction
    kyc_name = db.Column(db.String(120))
    kyc_aadhar = db.Column(db.String(20))
    kyc_mobile = db.Column(db.String(20))
    kyc_address = db.Column(db.String(200))
    upload_id = db.Column(db.Integer, db.ForeignKey("uploaded_file.id"))

    __table_args__ = (
        db.Index("idx_transaction_ack_no", "ack_no"),
        db.Index("idx_transaction_put_on_hold", "put_on_hold_txn_id"),
        # Cross-case mule-account detection groups by to_account (Feature A3).
        db.Index("idx_transaction_to_account", "to_account"),
    )


class POHRefundDetails(db.Model):
    """
    Persists refund details for Put-On-Hold transactions separately
    so they are not lost when the main Excel file is re-uploaded.
    """

    id = db.Column(db.Integer, primary_key=True)
    ack_no = db.Column(db.String(100), index=True)
    txn_id = db.Column(db.String(100), index=True)  # Corresponds to put_on_hold_txn_id
    court_order_date = db.Column(db.String(20))
    refund_status = db.Column(db.String(50))
    refund_amount = db.Column(db.Float)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (db.UniqueConstraint("ack_no", "txn_id", name="uq_poh_refund_details"),)


class MRMTracking(db.Model):
    """Money Restoration Module (MRM) progress for one put-on-hold transaction.

    The current snapshot: each of step1..step7 stores the completion date
    (yyyy-mm-dd string, blank/NULL = stage not yet reached) of that workflow stage.
    Stages are strictly sequential — step N can only be dated once step N-1 is dated.
    Step 6 ("Amount Refunded to Victim") additionally carries refund_type
    (FULL / PARTIAL) and refund_amount. Keyed by (ack_no, txn_id), where txn_id is
    the put_on_hold_txn_id, so the record survives a bank-sheet re-upload, exactly
    like POHRefundDetails. The full who/what/when history lives in MRMStatusLog.
    """

    id = db.Column(db.Integer, primary_key=True)
    ack_no = db.Column(db.String(100), index=True)
    txn_id = db.Column(db.String(100), index=True)  # put_on_hold_txn_id
    step1 = db.Column(db.String(20))
    step2 = db.Column(db.String(20))
    step3 = db.Column(db.String(20))
    step4 = db.Column(db.String(20))
    step5 = db.Column(db.String(20))
    step6 = db.Column(db.String(20))
    step7 = db.Column(db.String(20))
    refund_type = db.Column(db.String(10))  # FULL / PARTIAL (set with step6)
    refund_amount = db.Column(db.Float)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (db.UniqueConstraint("ack_no", "txn_id", name="uq_mrm_tracking"),)


class MRMStatusLog(db.Model):
    """Immutable audit trail of every MRM stage completion — one row per stage
    recorded, capturing WHAT stage, on WHICH completion date, by WHOM, and WHEN it
    was entered. Lets us reconstruct the full timeline of an MRM case for reporting.
    """

    id = db.Column(db.Integer, primary_key=True)
    ack_no = db.Column(db.String(100), index=True)
    txn_id = db.Column(db.String(100), index=True)  # put_on_hold_txn_id
    step = db.Column(db.Integer)  # 1..7
    step_label = db.Column(db.String(120))  # human-readable stage name
    date_completed = db.Column(db.String(20))  # officer-entered completion date
    refund_type = db.Column(db.String(10))  # FULL / PARTIAL (only on the refund stage)
    refund_amount = db.Column(db.Float)
    performed_by = db.Column(db.String(100))  # username who recorded it
    performed_role = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=utc_now)  # server time the entry was made


class KYCDetails(db.Model):
    """
    Persists KYC details separately.
    """

    id = db.Column(db.Integer, primary_key=True)
    txn_id = db.Column(db.String(100), unique=True, index=True)
    name = db.Column(db.String(120))
    aadhar = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    address = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)


class PasswordHistory(db.Model):
    """Stores previous password hashes so recent passwords cannot be reused
    (Feature B12: password expiry & reuse prevention)."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    password_hash = db.Column(db.Text)
    changed_at = db.Column(db.DateTime, default=utc_now)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password_hash = db.Column(db.Text)
    role = db.Column(db.String(50))
    name = db.Column(db.String(100))
    rank = db.Column(db.String(100))
    email = db.Column(db.String(120))
    # Optional override for displaying "No. of Files Uploaded" in admin view.
    # If NULL, the UI will show the computed count from UploadedFile.
    manual_upload_count = db.Column(db.Integer, nullable=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    account_locked_until = db.Column(db.DateTime, nullable=True)
    must_change_password = db.Column(db.Boolean, default=False)
    # Feature B13: show "last login" so users can spot unauthorised access.
    last_login_at = db.Column(db.DateTime, nullable=True)
    # Feature B12: password age tracking (NULL = never tracked; expiry not enforced).
    password_changed_at = db.Column(db.DateTime, nullable=True)
    # Feature B9: TOTP two-factor secret (NULL = 2FA not enabled for this user).
    totp_secret = db.Column(db.String(64), nullable=True)
    # Multi-admin isolation: for officers, points to their managing admin (User.id).
    # NULL on Admin and SuperAdmin accounts.
    admin_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    # SuperAdmin flag: a SuperAdmin is an Admin who can see all groups and all admins.
    # Exactly one account should carry this; it is seeded automatically on first run.
    is_superadmin = db.Column(db.Boolean, default=False, nullable=False, server_default="0")

    def set_password(self, password):
        validate_password(password)
        self._reject_recent_password(password)
        # Use scrypt where the platform supports it (strongest); otherwise fall back to
        # pbkdf2:sha256, which works on every Python (e.g. 3.9 / OpenSSL built without scrypt).
        method = "scrypt" if hasattr(hashlib, "scrypt") else "pbkdf2:sha256"
        # Archive the outgoing hash so reuse of recent passwords can be blocked.
        if self.password_hash and self.id is not None:
            db.session.add(PasswordHistory(user_id=self.id, password_hash=self.password_hash))
        self.password_hash = generate_password_hash(password, method=method)
        self.password_changed_at = utc_now()

    def _reject_recent_password(self, password):
        """Raise ValueError if `password` matches the current or a recent password."""
        candidates = [self.password_hash] if self.password_hash else []
        if self.id is not None:
            recent = (
                PasswordHistory.query.filter_by(user_id=self.id)
                .order_by(PasswordHistory.changed_at.desc())
                .limit(PASSWORD_HISTORY_LIMIT)
                .all()
            )
            candidates.extend(h.password_hash for h in recent)
        for old_hash in candidates:
            try:
                matched = check_password_hash(old_hash, password)
            except Exception:
                matched = False
            if matched:
                raise ValueError(f"New password must not match any of your last {PASSWORD_HISTORY_LIMIT} passwords")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    data = db.Column(db.LargeBinary)
    uploader = db.Column(db.String(100))  # session['username']
    mimetype = db.Column(db.String(100))
    upload_time = db.Column(db.DateTime, default=utc_now)
    transaction_count = db.Column(db.Integer, default=0)
    transaction = db.relationship("Transaction", backref="upload", uselist=False)


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ack_no = db.Column(db.String(50), unique=True, nullable=False)
    file_name = db.Column(db.String(200))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"))
    upload_time = db.Column(db.DateTime)
    # Feature A1: case workflow state — one of CASE_STATUSES.
    status = db.Column(db.String(30), default="Open")
    # Multi-admin isolation: which admin group owns this case.
    # Set to the uploading admin's id (or the officer's admin_id) at upload time.
    # NULL means visible to all admins (legacy rows from before isolation was introduced).
    owner_admin_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)


class CaseNote(db.Model):
    """Officer-written investigation notes per case (Feature A4: notes & timeline)."""

    id = db.Column(db.Integer, primary_key=True)
    ack_no = db.Column(db.String(100), index=True, nullable=False)
    author = db.Column(db.String(100))  # username
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now)


class UsageLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    role = db.Column(db.String(50))
    action = db.Column(db.String(100))
    filename = db.Column(db.String(255))
    ack_no = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=utc_now)

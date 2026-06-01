import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-local-testing'
    
    # Database paths
    secure_base = os.environ.get('FUNDTRAIL_DATA_DIR')
    if not secure_base:
        # Assuming app root is main/
        secure_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
    
    os.makedirs(secure_base, exist_ok=True)
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f"sqlite:///{os.path.join(secure_base, 'fundtrail.db')}"
    SQLALCHEMY_BINDS = {
        'poh_store': f'sqlite:///{os.path.join(secure_base, 'poh_refund_details.db')}',
        'kyc_store': f'sqlite:///{os.path.join(secure_base, 'kyc_details.db')}'
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')
    
    # Session Security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_NAME = 'session'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_REFRESH_EACH_REQUEST = False
    
    # Rate Limiting
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_DEFAULT_LIMITS = ["200 per day", "50 per hour"]

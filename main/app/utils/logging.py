from flask import session
from ..extensions import db
from ..models import UsageLog
import logging

logger = logging.getLogger(__name__)

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

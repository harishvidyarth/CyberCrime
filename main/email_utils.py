import os
from datetime import datetime, timezone

try:
    import resend
except ImportError:  # pragma: no cover
    resend = None


def _send_email(to_email: str, subject: str, html: str):
    if resend is None:
        return None
    resend.api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend.api_key:
        return None
    params = {
        "from": os.environ.get("RESEND_FROM_EMAIL", "noreply@fundtrail.app"),
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    return resend.Emails.send(params)


def send_password_reset(to_email: str, reset_link: str):
    return _send_email(
        to_email,
        "FundTrail - Password Reset",
        f"<a href='{reset_link}'>Reset your password</a>",
    )


def send_integration_test_email(to_email: str):
    sent_at = datetime.now(timezone.utc).isoformat()
    return _send_email(
        to_email,
        "FundTrail Resend integration test",
        f"<p>This is a FundTrail integration test email sent at {sent_at}.</p>",
    )

"""Send outreach emails through your own email account (SMTP).

Nothing is sent unless you configure SELLER_EMAIL + SELLER_EMAIL_APP_PASSWORD
and click "Send" in the app. There is no fully-automatic background sending.
Uses the Python standard library only (smtplib) — no third-party service.
"""
import smtplib
import ssl
from email.message import EmailMessage

from .config import (SELLER_EMAIL, SELLER_EMAIL_APP_PASSWORD, SELLER_NAME,
                     SMTP_HOST, SMTP_PORT)


def is_configured() -> bool:
    """True if we have enough to send (address + app password)."""
    return bool(SELLER_EMAIL and SELLER_EMAIL_APP_PASSWORD)


def verify_login() -> tuple[bool, str]:
    """Check the SMTP credentials without sending anything."""
    if not is_configured():
        return False, "Email sending is not configured."
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.starttls(context=ctx)
            s.login(SELLER_EMAIL, SELLER_EMAIL_APP_PASSWORD)
        return True, "Login OK."
    except smtplib.SMTPAuthenticationError:
        return False, ("Login rejected. For Gmail you must use an App Password "
                       "(not your normal password), with 2-Step Verification on.")
    except Exception as exc:
        return False, f"Could not connect: {exc}"


def send_email(to_address: str, subject: str, body: str) -> None:
    """Send one plain-text email. Raises on failure."""
    if not is_configured():
        raise RuntimeError("Email sending is not configured.")
    msg = EmailMessage()
    from_name = SELLER_NAME or SELLER_EMAIL
    msg["From"] = f"{from_name} <{SELLER_EMAIL}>"
    msg["To"] = to_address
    msg["Subject"] = subject
    msg["Reply-To"] = SELLER_EMAIL
    msg.set_content(body)

    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.starttls(context=ctx)
        s.login(SELLER_EMAIL, SELLER_EMAIL_APP_PASSWORD)
        s.send_message(msg)

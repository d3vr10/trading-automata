"""Email notification service using SMTP."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserSetting

logger = logging.getLogger(__name__)

# SMTP config from env
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() == "true"


def is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASS)


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an email via SMTP. Returns True on success."""
    if not is_configured():
        logger.debug("SMTP not configured, skipping email")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        if SMTP_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, to, msg.as_string())
        server.quit()
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


async def get_notification_prefs(db: AsyncSession, user_id: int) -> dict:
    """Get notification preferences for a user."""
    result = await db.execute(
        select(UserSetting).where(
            UserSetting.user_id == user_id,
            UserSetting.key.like("notify_%"),
        )
    )
    settings = result.scalars().all()
    prefs = {
        "notify_trade_executed": True,
        "notify_bot_error": True,
        "notify_bot_stopped": True,
    }
    for s in settings:
        prefs[s.key] = s.value == "true"
    return prefs


async def set_notification_pref(
    db: AsyncSession, user_id: int, key: str, enabled: bool,
) -> None:
    """Set a notification preference."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(UserSetting).values(
        user_id=user_id, key=key, value="true" if enabled else "false",
    ).on_conflict_do_update(
        index_elements=["user_id", "key"],
        set_={"value": "true" if enabled else "false"},
    )
    await db.execute(stmt)
    await db.commit()


async def get_user_email(db: AsyncSession, user_id: int) -> Optional[str]:
    """Get email for a user."""
    result = await db.execute(select(User.email).where(User.id == user_id))
    return result.scalar()


def build_trade_email(bot_name: str, data: dict) -> tuple[str, str]:
    """Build trade notification email. Returns (subject, html)."""
    action = data.get("action", "TRADE").upper()
    symbol = data.get("symbol", "?")
    price = data.get("price", 0)
    quantity = data.get("quantity", "?")
    subject = f"[{bot_name}] {action} {symbol} at ${price}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 500px;">
      <h2 style="color: #10b981;">{action} Executed</h2>
      <table style="width: 100%; border-collapse: collapse;">
        <tr><td style="padding: 8px; color: #888;">Bot</td><td style="padding: 8px; font-weight: bold;">{bot_name}</td></tr>
        <tr><td style="padding: 8px; color: #888;">Symbol</td><td style="padding: 8px; font-weight: bold;">{symbol}</td></tr>
        <tr><td style="padding: 8px; color: #888;">Action</td><td style="padding: 8px; font-weight: bold;">{action}</td></tr>
        <tr><td style="padding: 8px; color: #888;">Price</td><td style="padding: 8px; font-weight: bold;">${price}</td></tr>
        <tr><td style="padding: 8px; color: #888;">Quantity</td><td style="padding: 8px; font-weight: bold;">{quantity}</td></tr>
      </table>
    </div>
    """
    return subject, html


def build_error_email(bot_name: str, data: dict) -> tuple[str, str]:
    """Build error notification email."""
    message = data.get("message", "Unknown error")
    subject = f"[{bot_name}] Error: {message[:80]}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 500px;">
      <h2 style="color: #ef4444;">Bot Error</h2>
      <table style="width: 100%; border-collapse: collapse;">
        <tr><td style="padding: 8px; color: #888;">Bot</td><td style="padding: 8px; font-weight: bold;">{bot_name}</td></tr>
        <tr><td style="padding: 8px; color: #888;">Error</td><td style="padding: 8px; color: #ef4444;">{message}</td></tr>
      </table>
    </div>
    """
    return subject, html


def build_status_email(bot_name: str, data: dict) -> tuple[str, str]:
    """Build status change notification email."""
    status = data.get("status", "?")
    subject = f"[{bot_name}] Status: {status}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 500px;">
      <h2 style="color: #f59e0b;">Bot Status Changed</h2>
      <table style="width: 100%; border-collapse: collapse;">
        <tr><td style="padding: 8px; color: #888;">Bot</td><td style="padding: 8px; font-weight: bold;">{bot_name}</td></tr>
        <tr><td style="padding: 8px; color: #888;">New Status</td><td style="padding: 8px; font-weight: bold;">{status}</td></tr>
      </table>
    </div>
    """
    return subject, html

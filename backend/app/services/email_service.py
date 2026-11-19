"""
Transactional Email Delivery Service (Password Reset & Account Verification).

Uses standard SMTP (smtplib + STARTTLS) when SMTP_HOST is configured in environment
variables. In local development when SMTP_HOST is unconfigured, logs a clearly
labelled development-only reset/verification link to server logs and returns
delivery_mode='development_console' so the system never falsely claims SMTP email
was delivered.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _send_email(to_email: str, subject: str, text_body: str, html_body: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.smtp_host.strip():
        logger.warning(
            "[DEV-ONLY EMAIL FALLBACK — SMTP NOT CONFIGURED] To: %s | Subject: %s\n%s",
            to_email,
            subject,
            text_body,
        )
        return {
            "delivered_via_smtp": False,
            "delivery_mode": "development_console",
            "note": (
                "SMTP_HOST is not configured. Reset/verification link logged on backend console "
                "for local development only."
            ),
        }

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
        return {"delivered_via_smtp": True, "delivery_mode": "smtp", "note": "Email dispatched via SMTP."}
    except Exception as exc:
        logger.error("SMTP delivery failed for %s: %s", to_email, exc)
        return {
            "delivered_via_smtp": False,
            "delivery_mode": "smtp_error",
            "note": f"SMTP send error: {exc}",
        }


def send_password_reset_email(to_email: str, full_name: str, raw_token: str) -> dict[str, Any]:
    """Send password-reset email (or dev console link when SMTP is unconfigured)."""
    settings = get_settings()
    reset_url = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={raw_token}"
    subject = "MEDILOGIX — Password Reset Request"
    text_body = (
        f"Hello {full_name},\n\n"
        f"A password reset was requested for your MEDILOGIX account.\n"
        f"Open the link below within {settings.password_reset_expire_minutes} minutes:\n\n"
        f"{reset_url}\n\n"
        f"If you did not request this reset, you can safely ignore this message.\n"
        f"— MEDILOGIX Healthcare Logistics Platform\n"
    )
    html_body = (
        f"<div style='font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#0f172a'>"
        f"<div style='background:#0b162c;color:#ffffff;padding:16px 24px;border-radius:8px 8px 0 0'>"
        f"<h2 style='margin:0;font-size:18px'>MEDILOGIX Password Recovery</h2></div>"
        f"<div style='border:1px solid #e2e8f0;padding:24px;border-radius:0 0 8px 8px'>"
        f"<p>Hello <strong>{full_name}</strong>,</p>"
        f"<p>A password reset was requested for your MEDILOGIX account. This single-use link expires in "
        f"<strong>{settings.password_reset_expire_minutes} minutes</strong>.</p>"
        f"<p style='margin:24px 0'><a href='{reset_url}' style='background:#0284c7;color:#fff;"
        f"padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:bold'>Reset Password</a></p>"
        f"<p style='font-size:12px;color:#64748b'>If you did not request this, please ignore this email.</p>"
        f"</div></div>"
    )
    result = _send_email(to_email, subject, text_body, html_body)
    if settings.app_env == "development" and not result["delivered_via_smtp"]:
        result["dev_reset_url"] = reset_url
    return result


def send_verification_email(to_email: str, full_name: str, raw_token: str) -> dict[str, Any]:
    """Send account email-verification link (or dev console link when SMTP is unconfigured)."""
    settings = get_settings()
    verify_url = f"{settings.frontend_base_url.rstrip('/')}/verify-email?token={raw_token}"
    subject = "MEDILOGIX — Verify Your Email Address"
    text_body = (
        f"Hello {full_name},\n\n"
        f"Thank you for registering with MEDILOGIX. Verify your email address using the link below:\n\n"
        f"{verify_url}\n\n"
        f"Note: Hospital, Warehouse, and Delivery accounts also require Administrator approval before sign-in.\n"
    )
    html_body = (
        f"<div style='font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#0f172a'>"
        f"<div style='background:#0b162c;color:#ffffff;padding:16px 24px;border-radius:8px 8px 0 0'>"
        f"<h2 style='margin:0;font-size:18px'>MEDILOGIX Account Verification</h2></div>"
        f"<div style='border:1px solid #e2e8f0;padding:24px;border-radius:0 0 8px 8px'>"
        f"<p>Hello <strong>{full_name}</strong>,</p>"
        f"<p>Click below to verify your email address. An administrator will also review and approve your registration.</p>"
        f"<p style='margin:24px 0'><a href='{verify_url}' style='background:#0d9488;color:#fff;"
        f"padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:bold'>Verify Email</a></p>"
        f"</div></div>"
    )
    result = _send_email(to_email, subject, text_body, html_body)
    if settings.app_env == "development" and not result["delivered_via_smtp"]:
        result["dev_verify_url"] = verify_url
    return result

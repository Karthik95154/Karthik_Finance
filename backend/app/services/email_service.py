import asyncio
import logging
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

# Basic RFC 5322 compliant email regex pattern
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class EmailService:
    """Outbound transactional email service for user invitations and system notifications."""

    @staticmethod
    def validate_email_format(email: str) -> bool:
        """Validates basic email address syntax."""
        if not email or not isinstance(email, str):
            return False
        clean = email.strip()
        if len(clean) > 254:
            return False
        return bool(EMAIL_REGEX.match(clean))

    @staticmethod
    def _send_smtp_sync(
        recipient_email: str,
        subject: str,
        text_content: str,
        html_content: str
    ) -> Tuple[bool, Optional[str]]:
        """Synchronous SMTP email delivery helper (executed via asyncio.to_thread)."""
        smtp_host = (settings.SMTP_HOST or "").strip()
        smtp_port = settings.SMTP_PORT or 587
        smtp_user = (settings.SMTP_USERNAME or "").strip()
        smtp_pass = settings.SMTP_PASSWORD or ""
        from_email = (settings.SMTP_FROM_EMAIL or smtp_user or "no-reply@sakshi.ai").strip()

        if not smtp_host or not smtp_user:
            logger.warning(
                f"[SMTP UNCONFIGURED] Cannot send email to {recipient_email}. "
                "SMTP_HOST and SMTP_USERNAME must be set in .env."
            )
            return False, "SMTP server is not configured in settings."

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = recipient_email

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            logger.info(f"[EMAIL DELIVERED] Successfully sent '{subject}' to {recipient_email}")
            return True, None
        except smtplib.SMTPAuthenticationError as exc:
            logger.error(f"[SMTP AUTH ERROR] Failed to authenticate with SMTP server for {recipient_email}: {exc}")
            return False, "SMTP authentication failed."
        except smtplib.SMTPException as exc:
            logger.error(f"[SMTP ERROR] Failed to deliver email to {recipient_email}: {exc}")
            return False, "SMTP delivery error occurred."
        except Exception as exc:
            logger.error(f"[EMAIL ERROR] Unexpected failure while sending email to {recipient_email}: {exc}")
            return False, "Email connection timed out or failed."

    @classmethod
    async def send_invitation_email(
        cls,
        recipient_email: str,
        recipient_name: Optional[str],
        invitation_url: str,
        expires_at: datetime
    ) -> Tuple[bool, Optional[str]]:
        """
        Sends an automated user invitation email with the secure invitation link.
        Returns: (success: bool, error_message: Optional[str])
        """
        clean_email = recipient_email.strip().lower()
        if not cls.validate_email_format(clean_email):
            logger.warning(f"[INVALID EMAIL] Rejecting invalid email format: '{recipient_email}'")
            return False, "The email address provided is invalid."

        display_name = recipient_name.strip() if recipient_name and recipient_name.strip() else clean_email.split("@")[0].capitalize()
        formatted_expiry = expires_at.strftime("%B %d, %Y at %I:%M %p UTC")
        subject = "You're invited to Sakshi Finance"

        plain_text = f"""Hello {display_name},

You have been invited to join Sakshi Finance.

Click the link below to create your account and set your password:
{invitation_url}

This invitation will expire after {formatted_expiry}.

If you were not expecting this invitation, you can ignore this email.

Regards,
Sakshi Finance
"""

        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f5f5f7; margin: 0; padding: 30px 15px; color: #1d1d1f; }}
        .card {{ max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e5e5ea; padding: 36px 32px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); }}
        .brand {{ display: flex; align-items: center; gap: 10px; margin-bottom: 24px; }}
        .brand-icon {{ width: 36px; height: 36px; background: linear-gradient(135deg, #0071e3 0%, #005bb5 100%); border-radius: 10px; color: #fff; font-weight: bold; display: flex; align-items: center; justify-content: center; font-size: 18px; }}
        .brand-title {{ font-size: 18px; font-weight: 700; color: #1d1d1f; margin: 0; }}
        h1 {{ font-size: 20px; font-weight: 700; margin-top: 0; margin-bottom: 12px; color: #1d1d1f; }}
        p {{ font-size: 14px; line-height: 1.6; color: #515154; margin-bottom: 20px; }}
        .btn-container {{ text-align: center; margin: 28px 0; }}
        .btn {{ display: inline-block; background-color: #0071e3; color: #ffffff !important; text-decoration: none; font-weight: 600; font-size: 14px; padding: 12px 28px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0, 113, 227, 0.25); }}
        .footer {{ margin-top: 28px; padding-top: 20px; border-top: 1px solid #f2f2f7; font-size: 12px; color: #86868b; line-height: 1.5; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="brand">
            <div class="brand-icon">S</div>
            <div class="brand-title">Sakshi Finance</div>
        </div>
        <h1>You're invited to Sakshi Finance</h1>
        <p>Hello <strong>{display_name}</strong>,</p>
        <p>You have been invited to join Sakshi Finance. Click the button below to create your account and set your password.</p>
        
        <div class="btn-container">
            <a href="{invitation_url}" class="btn">Accept Invitation</a>
        </div>
        
        <p style="font-size: 13px; color: #86868b;">This invitation will expire after <strong>{formatted_expiry}</strong>.</p>
        
        <div class="footer">
            If you were not expecting this invitation, you can safely ignore this email.<br><br>
            Regards,<br>
            <strong>Sakshi Finance Team</strong>
        </div>
    </div>
</body>
</html>
"""

        # Execute SMTP send in a thread to keep async event loop non-blocking
        return await asyncio.to_thread(
            cls._send_smtp_sync,
            clean_email,
            subject,
            plain_text,
            html_body
        )

    @classmethod
    async def send_otp_email(
        cls,
        recipient_email: str,
        otp: str,
        expires_in_minutes: int = 10
    ) -> Tuple[bool, Optional[str]]:
        """
        Delivers a 6-digit email verification OTP to the specified invited email address.
        NEVER logs raw OTP in logs.
        """
        clean_email = recipient_email.strip().lower()
        if not cls.validate_email_format(clean_email):
            logger.warning(f"[INVALID EMAIL] Rejecting OTP email to invalid email format: '{recipient_email}'")
            return False, "The email address provided is invalid."

        subject = f"{otp} is your Sakshi Finance verification code"

        plain_text = f"""Your verification code for Sakshi Finance is: {otp}

This code will expire in {expires_in_minutes} minutes.

If you did not request this verification code, please ignore this email.

Regards,
Sakshi Finance Security
"""

        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f5f5f7; margin: 0; padding: 30px 15px; color: #1d1d1f; }}
        .card {{ max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e5e5ea; padding: 36px 32px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); }}
        .brand {{ display: flex; align-items: center; gap: 10px; margin-bottom: 24px; }}
        .brand-icon {{ width: 36px; height: 36px; background: linear-gradient(135deg, #0071e3 0%, #005bb5 100%); border-radius: 10px; color: #fff; font-weight: bold; display: flex; align-items: center; justify-content: center; font-size: 18px; }}
        .brand-title {{ font-size: 18px; font-weight: 700; color: #1d1d1f; margin: 0; }}
        h1 {{ font-size: 20px; font-weight: 700; margin-top: 0; margin-bottom: 12px; color: #1d1d1f; }}
        p {{ font-size: 14px; line-height: 1.6; color: #515154; margin-bottom: 20px; }}
        .otp-box {{ text-align: center; margin: 24px 0; background: #f0f7ff; border: 1px solid #0071e3; border-radius: 12px; padding: 18px; letter-spacing: 8px; font-size: 32px; font-weight: 800; color: #0071e3; font-family: monospace; }}
        .footer {{ margin-top: 28px; padding-top: 20px; border-top: 1px solid #f2f2f7; font-size: 12px; color: #86868b; line-height: 1.5; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="brand">
            <div class="brand-icon">S</div>
            <div class="brand-title">Sakshi Finance</div>
        </div>
        <h1>Email Verification Code</h1>
        <p>Use the 6-digit code below to verify your email address and proceed with account creation:</p>
        
        <div class="otp-box">{otp}</div>
        
        <p style="font-size: 13px; color: #86868b;">This code is single-use and will expire in <strong>{expires_in_minutes} minutes</strong>.</p>
        
        <div class="footer">
            If you did not request this verification code, please ignore this email.<br><br>
            Regards,<br>
            <strong>Sakshi Finance Security Team</strong>
        </div>
    </div>
</body>
</html>
"""

        logger.info(f"[OTP DISPATCHED] Sending verification code to target email: {clean_email}")
        return await asyncio.to_thread(
            cls._send_smtp_sync,
            clean_email,
            subject,
            plain_text,
            html_body
        )

    @classmethod
    async def send_verification_otp(
        cls,
        to_email: str,
        otp: str,
        recipient_name: Optional[str] = None,
        expires_in_minutes: int = 15
    ) -> Tuple[bool, Optional[str]]:
        """Alias for send_otp_email supporting named argument conventions."""
        return await cls.send_otp_email(to_email, otp, expires_in_minutes)


email_service = EmailService()

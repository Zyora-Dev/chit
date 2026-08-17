import html

import httpx

from app.core.config import settings


class EmailConfigurationError(RuntimeError):
    pass


async def send_otp_email(recipient: str, otp: str, purpose: str) -> None:
    if not settings.zeptomail_send_token or not settings.zeptomail_from_email:
        raise EmailConfigurationError("ZeptoMail credentials are not configured")

    action = "verify your email" if purpose == "email_verification" else "reset your password"
    safe_otp = html.escape(otp)
    payload = {
        "from": {
            "address": settings.zeptomail_from_email,
            "name": settings.zeptomail_from_name,
        },
        "to": [{"email_address": {"address": recipient, "name": recipient}}],
        "subject": f"Your zChit verification code: {otp}",
        "htmlbody": (
            "<div style='font-family:Inter,Arial,sans-serif;color:#111827'>"
            "<h2 style='color:#059669'>zChit</h2>"
            f"<p>Use this code to {action}:</p>"
            f"<p style='font-size:28px;font-weight:700;letter-spacing:6px'>{safe_otp}</p>"
            f"<p>This code expires in {settings.otp_expire_minutes} minutes.</p>"
            "<p>If you did not request this, ignore this email.</p>"
            "</div>"
        ),
        "track_clicks": False,
        "track_opens": False,
    }
    send_token = settings.zeptomail_send_token.strip()
    if send_token.lower().startswith("zoho-enczapikey "):
        send_token = send_token.split(maxsplit=1)[1]

    headers = {
        "Authorization": f"Zoho-enczapikey {send_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(settings.zeptomail_api_url, json=payload, headers=headers)
        response.raise_for_status()

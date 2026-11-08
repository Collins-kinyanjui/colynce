"""Send consultation notifications using a verified sender via the Resend API.

Set RESEND_API_KEY, NOTIFY_EMAIL, and EMAIL_FROM in the hosting environment.
No customer data or API credentials are sent to GitHub.
"""
import logging
import os
from html import escape
import httpx

logger = logging.getLogger(__name__)

def configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY") and os.getenv("NOTIFY_EMAIL") and os.getenv("EMAIL_FROM"))

async def send_lead_notice(lead: dict) -> None:
    if not configured():
        logger.warning("Email notification skipped: RESEND_API_KEY, NOTIFY_EMAIL or EMAIL_FROM is missing")
        return
    details = {
        "Name": lead["name"], "Business": lead["business"], "Email": lead["email"],
        "Interest": lead["interest"], "Message": lead["message"], "Reference": lead["reference"]
    }
    html = "<h2>New COKIT Digital consultation request</h2>" + "".join(
        f"<p><strong>{escape(key)}:</strong> {escape(str(value))}</p>" for key,value in details.items()
    ) + "<p>Manage leads in your COKIT Digital admin dashboard.</p>"
    text = "New COKIT Digital consultation request\n\n" + "\n".join(
        f"{key}: {value}" for key,value in details.items()
    )
    body = {
        "from": os.environ["EMAIL_FROM"],
        "to": [os.environ["NOTIFY_EMAIL"]],
        "subject": "New COKIT Digital inquiry: " + lead["interest"][:80],
        "html": html,
        "text": text,
        "reply_to": lead["email"],
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": "Bearer " + os.environ["RESEND_API_KEY"],
                         "Content-Type": "application/json"},
                json=body,
            )
            response.raise_for_status()
        logger.info("Consultation notification accepted for lead %s", lead["reference"])
    except Exception:
        logger.exception("Consultation notification failed for lead %s", lead["reference"])

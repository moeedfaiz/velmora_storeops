from typing import Dict, Any

def send_email_stub(to: str, subject: str, body: str) -> Dict[str, Any]:
    # In production: integrate with SES/SendGrid/etc.
    return {"status": "queued", "to": to, "subject": subject, "preview": body[:120]}

def send_sms_stub(to: str, body: str) -> Dict[str, Any]:
    # In production: Twilio/etc.
    return {"status": "queued", "to": to, "preview": body[:120]}

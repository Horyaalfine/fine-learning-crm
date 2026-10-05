"""Thin wrapper around the Twilio SDK so the rest of the app doesn't need to
know about Twilio specifics, and so sending degrades gracefully in dev
(no credentials configured) instead of crashing.
"""
from flask import current_app


class SmsNotConfigured(Exception):
    pass


def send_sms(to_number: str, body: str) -> str:
    """Send one SMS. Returns the Twilio message SID on success.

    Raises SmsNotConfigured if Twilio credentials aren't set, or whatever
    the Twilio client raises on a send failure (caller should catch and
    record it against the recipient).
    """
    sid = current_app.config.get("TWILIO_ACCOUNT_SID")
    token = current_app.config.get("TWILIO_AUTH_TOKEN")
    from_number = current_app.config.get("TWILIO_FROM_NUMBER")
    messaging_service_sid = current_app.config.get("TWILIO_MESSAGING_SERVICE_SID")

    if not sid or not token or not (from_number or messaging_service_sid):
        raise SmsNotConfigured(
            "Twilio is not configured (set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
            "and TWILIO_FROM_NUMBER or TWILIO_MESSAGING_SERVICE_SID)."
        )

    from twilio.rest import Client

    client = Client(sid, token)
    kwargs = {"to": to_number, "body": body}
    if messaging_service_sid:
        kwargs["messaging_service_sid"] = messaging_service_sid
    else:
        kwargs["from_"] = from_number

    message = client.messages.create(**kwargs)
    return message.sid

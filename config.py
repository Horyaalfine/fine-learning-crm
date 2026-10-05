import os


def _normalize_db_url(url: str) -> str:
    # Railway/Heroku-style URLs sometimes use postgres:// which SQLAlchemy rejects.
    # Also force the psycopg2 driver explicitly: newer SQLAlchemy versions can
    # default a bare "postgresql://" URL to the psycopg (v3) dialect, which
    # isn't installed here (we use psycopg2-binary), causing a boot crash.
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key-change-me")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
        os.environ.get("DATABASE_URL", "sqlite:///local.db")
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Public URL of the Fine Learning booking landing page, used in SMS templates
    LANDING_PAGE_URL = os.environ.get("LANDING_PAGE_URL", "https://book.finelearning.co.uk")

    # Shared secret the landing page form must send so /api/leads can't be spammed
    # by anyone who finds the endpoint URL.
    LEAD_API_KEY = os.environ.get("LEAD_API_KEY", "")

    # One-time bootstrap secret for POST /setup, which creates the first admin
    # account. Only works while the users table is empty - see auth.py.
    SETUP_TOKEN = os.environ.get("SETUP_TOKEN", "")

    # Twilio
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")
    TWILIO_MESSAGING_SERVICE_SID = os.environ.get("TWILIO_MESSAGING_SERVICE_SID", "")

    # Comma-separated origins allowed to POST to /api/leads (the landing page's own domain)
    ALLOWED_LEAD_ORIGINS = [
        o.strip()
        for o in os.environ.get(
            "ALLOWED_LEAD_ORIGINS", "https://book.finelearning.co.uk"
        ).split(",")
        if o.strip()
    ]

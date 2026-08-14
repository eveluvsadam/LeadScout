"""Configuration, read from environment variables (see .env.example)."""
import os

from dotenv import load_dotenv

# Load a local .env file if present (your private details live here, not in git).
load_dotenv()

# Where the SQLite file lives (used when DATABASE_URL is not set).
DB_PATH = os.getenv("DB_PATH", "data/leadscout.db")

# Database backend. Defaults to a local SQLite file. Set DATABASE_URL to a
# Postgres URL (e.g. Render's) to use a persistent hosted database instead.
# Render/Heroku give "postgres://..."; we normalise it for SQLAlchemy.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]
if not DATABASE_URL:
    DATABASE_URL = f"sqlite:///{DB_PATH}"

# OpenStreetMap services (100% free, no API key, no billing).
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")

# Several free public Overpass mirrors. We try them in order until one answers,
# so a busy or rate-limited server doesn't break a search. Override with a
# comma-separated OVERPASS_URLS, or a single OVERPASS_URL.
_DEFAULT_OVERPASS = ",".join([
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
])
OVERPASS_URLS = [
    u.strip() for u in
    os.getenv("OVERPASS_URLS", os.getenv("OVERPASS_URL", _DEFAULT_OVERPASS)).split(",")
    if u.strip()
]

# Nominatim's usage policy asks for an identifying User-Agent with contact info.
USER_AGENT = os.getenv("USER_AGENT", "LeadScout/1.0 (self-hosted lead tool)")

# Your details, used to personalise outreach emails and call scripts.
# Set these in a local .env file (see .env.example) — never commit real values.
# Blank fields keep the editable [ ] placeholder in the generated text.
SELLER_NAME = os.getenv("SELLER_NAME", "")
SELLER_COMPANY = os.getenv("SELLER_COMPANY", "")
SELLER_PHONE = os.getenv("SELLER_PHONE", "")
SELLER_EMAIL = os.getenv("SELLER_EMAIL", "")

# Sending email from the app (batch send). Uses your email provider's SMTP.
# For Gmail: turn on 2-Step Verification, create an "App Password", and put it
# in SELLER_EMAIL_APP_PASSWORD in your .env. Never commit it.
SELLER_EMAIL_APP_PASSWORD = os.getenv("SELLER_EMAIL_APP_PASSWORD", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SEND_DELAY_SECONDS = float(os.getenv("SEND_DELAY_SECONDS", "1.5"))  # gap between sends
MAX_BATCH_SEND = int(os.getenv("MAX_BATCH_SEND", "25"))  # safety cap per batch

# Optional password gate. When set, every page requires this password (HTTP
# Basic auth). Leave blank for local use (the Mac app). ALWAYS set it before
# hosting the app on the public internet, since there is no user login.
APP_PASSWORD = os.getenv("APP_PASSWORD", "")

# Set ADMIN_RESET=1 to clear the admin password on startup (then remove it).
# Useful on hosts where you can't open a terminal to run `python -m app.reset_admin`.
ADMIN_RESET = os.getenv("ADMIN_RESET", "").lower() in ("1", "true", "yes")

# Safety caps so a single search stays fast and polite.
MAX_BUSINESSES = int(os.getenv("MAX_BUSINESSES", "60"))       # a single city
MAX_BUSINESSES_STATE = int(os.getenv("MAX_BUSINESSES_STATE", "250"))  # a whole state
ANALYZE_CONCURRENCY = int(os.getenv("ANALYZE_CONCURRENCY", "16"))  # parallel site checks
SITE_TIMEOUT = float(os.getenv("SITE_TIMEOUT", "8"))          # seconds per website fetch
OVERPASS_TIMEOUT = float(os.getenv("OVERPASS_TIMEOUT", "30"))
MAX_PAGE_BYTES = int(os.getenv("MAX_PAGE_BYTES", "500000"))   # stop downloading a page after this
# Broken-link checking is the slowest part of a scan (extra requests per site);
# off by default for speed. Set to "true" to include it.
CHECK_BROKEN_LINKS = os.getenv("CHECK_BROKEN_LINKS", "false").lower() == "true"

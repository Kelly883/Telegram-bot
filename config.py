import os
from pathlib import Path
from dotenv import load_dotenv

# Load variables from .env file if it exists (for local development)
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Database configuration: use DATABASE_URL if available (Postgres), otherwise SQLite
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    print(f"DEBUG: Original DATABASE_URL = {repr(DATABASE_URL)}")  # Debug log
    import re
    # Extract the actual URL from any surrounding text/quotes/commands
    url_match = re.search(r'(postgresql?://[^\s\'"]+)', DATABASE_URL)
    if url_match:
        DATABASE_URL = url_match.group(1)
    # Normalize Postgres connection schemes (handle case-insensitively)
    if DATABASE_URL.lower().startswith("psql://"):
        DATABASE_URL = "postgres://" + DATABASE_URL[len("psql://"):]
    print(f"DEBUG: Processed DATABASE_URL = {repr(DATABASE_URL)}")  # Debug log
    USE_POSTGRES = True
    DB_PATH = BASE_DIR / "bot.sqlite"
else:
    USE_POSTGRES = False
    # On Fly.io or Render, use appropriate directory for SQLite; locally, use project directory
    if os.getenv("FLY_APP_NAME"):
        DB_PATH = Path("/data") / "bot.sqlite"
    elif os.getenv("RENDER"):
        # On Render, use /opt/render/project/data for persistent storage (you'll need to add a disk)
        DB_PATH = Path("/opt/render/project/data") / "bot.sqlite"
        # Ensure directory exists
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    else:
        DB_PATH = BASE_DIR / "bot.sqlite"

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
FLUTTERWAVE_SECRET_KEY = os.getenv("FLUTTERWAVE_SECRET_KEY")
FLUTTERWAVE_PUBLIC_KEY = os.getenv("FLUTTERWAVE_PUBLIC_KEY")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYMENT_CALLBACK_URL = os.getenv("PAYMENT_CALLBACK_URL", "")
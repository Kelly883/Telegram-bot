import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BOT_TOKEN = os.getenv("BOT_TOKEN", "8698770745:AAE-MGAqzvoor1UNOS8dVnjBpCGN27iGK7U")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
FLUTTERWAVE_SECRET_KEY = os.getenv("FLUTTERWAVE_SECRET_KEY", "FLWSECK_TEST-e4d0a18f6a2c9a47529a1a819e4e3c6a-X")
FLUTTERWAVE_PUBLIC_KEY = os.getenv("FLUTTERWAVE_PUBLIC_KEY", "FLWPUBK_TEST-cf04a727bf95223bc0558bf3c3294c07-X")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "sk_test_02c971b7802c67b3460e3ccb34ce5b84110fa7b3")
PAYMENT_CALLBACK_URL = os.getenv("PAYMENT_CALLBACK_URL", "")
DB_PATH = BASE_DIR / "bot.sqlite"

import sqlite3
from contextlib import closing
from pathlib import Path

from config import DB_PATH

SQL_CREATE = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        country_code TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subscription_levels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price_ngn INTEGER NOT NULL,
        price_usd INTEGER NOT NULL,
        description TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        level_id INTEGER NOT NULL,
        start_date TEXT DEFAULT CURRENT_TIMESTAMP,
        expiry_date TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(level_id) REFERENCES subscription_levels(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(level_id) REFERENCES subscription_levels(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        level_id INTEGER NOT NULL,
        gateway TEXT NOT NULL,
        tx_ref TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(level_id) REFERENCES subscription_levels(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS verification_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_id INTEGER NOT NULL,
        tx_ref TEXT NOT NULL,
        verification_status TEXT NOT NULL,
        gateway_response TEXT,
        amount_match INTEGER NOT NULL,
        timestamp_valid INTEGER NOT NULL,
        fraud_flags TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(payment_id) REFERENCES payments(id)
    )
    """,
]


def init_db():
    Path(DB_PATH.parent).mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        for statement in SQL_CREATE:
            conn.execute(statement)
        conn.commit()


def _dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = _dict_factory
    return conn


def create_user(telegram_id: int, name: str, email: str, phone: str, country_code: str):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, name, email, phone, country_code) VALUES (?, ?, ?, ?, ?)",
            (telegram_id, name.strip(), email.strip().lower(), phone.strip(), country_code.strip()),
        )
        conn.commit()
        if cursor.lastrowid:
            return get_user_by_telegram_id(telegram_id)
        return get_user_by_telegram_id(telegram_id)


def get_user_by_telegram_id(telegram_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()


def get_user_by_id(user_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def list_users():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()


def create_subscription_level(name: str, price_ngn: int, price_usd: int, description: str):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO subscription_levels (name, price_ngn, price_usd, description) VALUES (?, ?, ?, ?)",
            (name.strip(), price_ngn, price_usd, description.strip()),
        )
        conn.commit()
        return cursor.lastrowid


def list_subscription_levels():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM subscription_levels ORDER BY id ASC").fetchall()


def get_subscription_level(level_id: int):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM subscription_levels WHERE id = ?", (level_id,)).fetchone()


def create_subscription(user_id: int, level_id: int, expiry_date: str):
    with get_connection() as conn:
        conn.execute("UPDATE subscriptions SET active = 0 WHERE user_id = ? AND active = 1", (user_id,))
        cursor = conn.execute(
            "INSERT INTO subscriptions (user_id, level_id, expiry_date, active) VALUES (?, ?, ?, 1)",
            (user_id, level_id, expiry_date),
        )
        conn.commit()
        return cursor.lastrowid


def get_active_subscription(user_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT s.*, l.name AS level_name, l.description FROM subscriptions s "
            "JOIN subscription_levels l ON s.level_id = l.id "
            "WHERE s.user_id = ? AND s.active = 1 ORDER BY s.expiry_date DESC LIMIT 1",
            (user_id,),
        ).fetchone()


def add_prediction(level_id: int, title: str, content: str):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO predictions (level_id, title, content) VALUES (?, ?, ?)",
            (level_id, title.strip(), content.strip()),
        )
        conn.commit()
        return cursor.lastrowid


def list_predictions_for_level(level_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM predictions WHERE level_id = ? ORDER BY created_at DESC",
            (level_id,),
        ).fetchall()


def record_payment(user_id: int, level_id: int, gateway: str, tx_ref: str, amount: float, currency: str, status: str):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO payments (user_id, level_id, gateway, tx_ref, amount, currency, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, level_id, gateway, tx_ref, amount, currency, status),
        )
        conn.commit()
        return cursor.lastrowid


def update_payment_status(tx_ref: str, status: str):
    with get_connection() as conn:
        conn.execute("UPDATE payments SET status = ? WHERE tx_ref = ?", (status, tx_ref))
        conn.commit()


def get_payment_by_ref(tx_ref: str):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM payments WHERE tx_ref = ?", (tx_ref,)).fetchone()


def get_pending_payment_by_user(user_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM payments WHERE user_id = ? AND status = 'PENDING' ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()


def get_all_pending_payments():
    """Get all pending payments for background verification"""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM payments WHERE status = 'PENDING' ORDER BY created_at ASC"
        ).fetchall()


def log_verification_attempt(payment_id: int, tx_ref: str, status: str, gateway_response: str, amount_match: bool, timestamp_valid: bool, fraud_flags: list):
    flags_str = ",".join(fraud_flags) if fraud_flags else ""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO verification_logs (payment_id, tx_ref, verification_status, gateway_response, amount_match, timestamp_valid, fraud_flags) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (payment_id, tx_ref, status, gateway_response[:500] if gateway_response else None, int(amount_match), int(timestamp_valid), flags_str),
        )
        conn.commit()


def export_users_csv(path: str):
    import csv
    users = list_users()
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Telegram ID", "Name", "Email", "Phone", "Country Code", "Registered"])
        for user in users:
            writer.writerow([user["telegram_id"], user["name"], user["email"], user["phone"], user["country_code"], user["created_at"]])
    return path

import sqlite3
from contextlib import closing
from pathlib import Path
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from config import USE_POSTGRES, DATABASE_URL, DB_PATH

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

# Postgres-compatible SQL (uses SERIAL instead of AUTOINCREMENT)
SQL_CREATE_POSTGRES = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        telegram_id INTEGER UNIQUE,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        country_code TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subscription_levels (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        price_ngn INTEGER NOT NULL,
        price_usd INTEGER NOT NULL,
        description TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subscriptions (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        level_id INTEGER NOT NULL,
        start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expiry_date TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(level_id) REFERENCES subscription_levels(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS predictions (
        id SERIAL PRIMARY KEY,
        level_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(level_id) REFERENCES subscription_levels(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        level_id INTEGER NOT NULL,
        gateway TEXT NOT NULL,
        tx_ref TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(level_id) REFERENCES subscription_levels(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS verification_logs (
        id SERIAL PRIMARY KEY,
        payment_id INTEGER NOT NULL,
        tx_ref TEXT NOT NULL,
        verification_status TEXT NOT NULL,
        gateway_response TEXT,
        amount_match INTEGER NOT NULL,
        timestamp_valid INTEGER NOT NULL,
        fraud_flags TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(payment_id) REFERENCES payments(id)
    )
    """,
]

def get_connection():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    if USE_POSTGRES:
        with closing(get_connection()) as conn:
            with closing(conn.cursor()) as cur:
                for stmt in SQL_CREATE_POSTGRES:
                    cur.execute(stmt)
            conn.commit()
    else:
        Path(DB_PATH.parent).mkdir(parents=True, exist_ok=True)
        with closing(get_connection()) as conn:
            for stmt in SQL_CREATE:
                conn.execute(stmt)
            conn.commit()

def create_user(telegram_id: int, name: str, email: str, phone: str, country_code: str):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute(
                    "INSERT INTO users (telegram_id, name, email, phone, country_code) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (telegram_id) DO NOTHING RETURNING id",
                    (telegram_id, name.strip(), email.strip().lower(), phone.strip(), country_code.strip()),
                )
                result = cur.fetchone()
                conn.commit()
                if result:
                    return get_user_by_telegram_id(telegram_id)
                return get_user_by_telegram_id(telegram_id)
        else:
            cur = conn.execute(
                "INSERT OR IGNORE INTO users (telegram_id, name, email, phone, country_code) VALUES (?, ?, ?, ?, ?)",
                (telegram_id, name.strip(), email.strip().lower(), phone.strip(), country_code.strip()),
            )
            conn.commit()
            if cur.lastrowid:
                return get_user_by_telegram_id(telegram_id)
            return get_user_by_telegram_id(telegram_id)

def get_user_by_telegram_id(telegram_id: int):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                return cur.fetchone()
        else:
            return conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()

def get_user_by_id(user_id: int):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                return cur.fetchone()
        else:
            return conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()

def list_users():
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("SELECT * FROM users ORDER BY created_at DESC")
                return cur.fetchall()
        else:
            return conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()

def create_subscription_plan(name: str, price_ngn: int, price_usd: int, description: str):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute(
                    "INSERT INTO subscription_levels (name, price_ngn, price_usd, description) VALUES (%s, %s, %s, %s) RETURNING id",
                    (name.strip(), price_ngn, price_usd, description.strip()),
                )
                result = cur.fetchone()
                conn.commit()
                return result['id']
        else:
            cur = conn.execute(
                "INSERT INTO subscription_levels (name, price_ngn, price_usd, description) VALUES (?, ?, ?, ?)",
                (name.strip(), price_ngn, price_usd, description.strip()),
            )
            conn.commit()
            return cur.lastrowid

def list_subscription_plans():
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("SELECT * FROM subscription_levels ORDER BY id ASC")
                return cur.fetchall()
        else:
            return conn.execute("SELECT * FROM subscription_levels ORDER BY id ASC").fetchall()

def get_subscription_plan(level_id: int):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("SELECT * FROM subscription_levels WHERE id = %s", (level_id,))
                return cur.fetchone()
        else:
            return conn.execute("SELECT * FROM subscription_levels WHERE id = ?", (level_id,)).fetchone()

def create_subscription(user_id: int, level_id: int, expiry_date: str):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("UPDATE subscriptions SET active = 0 WHERE user_id = %s AND active = 1", (user_id,))
                cur.execute(
                    "INSERT INTO subscriptions (user_id, level_id, expiry_date, active) VALUES (%s, %s, %s, 1) RETURNING id",
                    (user_id, level_id, expiry_date),
                )
                result = cur.fetchone()
                conn.commit()
                return result['id']
        else:
            conn.execute("UPDATE subscriptions SET active = 0 WHERE user_id = ? AND active = 1", (user_id,))
            cur = conn.execute(
                "INSERT INTO subscriptions (user_id, level_id, expiry_date, active) VALUES (?, ?, ?, 1)",
                (user_id, level_id, expiry_date),
            )
            conn.commit()
            return cur.lastrowid

def get_active_subscription(user_id: int):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute(
                    """SELECT s.*, l.name AS level_name, l.description 
                       FROM subscriptions s 
                       JOIN subscription_levels l ON s.level_id = l.id 
                       WHERE s.user_id = %s AND s.active = 1 
                       ORDER BY s.expiry_date DESC LIMIT 1""",
                    (user_id,),
                )
                return cur.fetchone()
        else:
            return conn.execute(
                """SELECT s.*, l.name AS level_name, l.description 
                   FROM subscriptions s 
                   JOIN subscription_levels l ON s.level_id = l.id 
                   WHERE s.user_id = ? AND s.active = 1 
                   ORDER BY s.expiry_date DESC LIMIT 1""",
                (user_id,),
            ).fetchone()

def add_prediction(level_id: int, title: str, content: str):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute(
                    "INSERT INTO predictions (level_id, title, content) VALUES (%s, %s, %s) RETURNING id",
                    (level_id, title.strip(), content.strip()),
                )
                result = cur.fetchone()
                conn.commit()
                return result['id']
        else:
            cur = conn.execute(
                "INSERT INTO predictions (level_id, title, content) VALUES (?, ?, ?)",
                (level_id, title.strip(), content.strip()),
            )
            conn.commit()
            return cur.lastrowid

def list_predictions_for_plan(level_id: int):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute(
                    "SELECT * FROM predictions WHERE level_id = %s ORDER BY created_at DESC",
                    (level_id,),
                )
                return cur.fetchall()
        else:
            return conn.execute(
                "SELECT * FROM predictions WHERE level_id = ? ORDER BY created_at DESC",
                (level_id,),
            ).fetchall()

def record_payment(user_id: int, level_id: int, gateway: str, tx_ref: str, amount: float, currency: str, status: str):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute(
                    "INSERT INTO payments (user_id, level_id, gateway, tx_ref, amount, currency, status) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (user_id, level_id, gateway, tx_ref, amount, currency, status),
                )
                result = cur.fetchone()
                conn.commit()
                return result['id']
        else:
            cur = conn.execute(
                "INSERT INTO payments (user_id, level_id, gateway, tx_ref, amount, currency, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, level_id, gateway, tx_ref, amount, currency, status),
            )
            conn.commit()
            return cur.lastrowid

def update_payment_status(tx_ref: str, status: str):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("UPDATE payments SET status = %s WHERE tx_ref = %s", (status, tx_ref))
                conn.commit()
        else:
            conn.execute("UPDATE payments SET status = ? WHERE tx_ref = ?", (status, tx_ref))
            conn.commit()

def get_payment_by_ref(tx_ref: str):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("SELECT * FROM payments WHERE tx_ref = %s", (tx_ref,))
                return cur.fetchone()
        else:
            return conn.execute("SELECT * FROM payments WHERE tx_ref = ?", (tx_ref,)).fetchone()

def get_pending_payment_by_user(user_id: int):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute(
                    "SELECT * FROM payments WHERE user_id = %s AND status = 'PENDING' ORDER BY created_at DESC LIMIT 1",
                    (user_id,),
                )
                return cur.fetchone()
        else:
            return conn.execute(
                "SELECT * FROM payments WHERE user_id = ? AND status = 'PENDING' ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()

def get_all_pending_payments():
    """Get all pending payments for background verification"""
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("SELECT * FROM payments WHERE status = 'PENDING' ORDER BY created_at ASC")
                return cur.fetchall()
        else:
            return conn.execute(
                "SELECT * FROM payments WHERE status = 'PENDING' ORDER BY created_at ASC"
            ).fetchall()

def log_verification_attempt(payment_id: int, tx_ref: str, status: str, gateway_response: str, amount_match: bool, timestamp_valid: bool, fraud_flags: list):
    flags_str = ",".join(fraud_flags) if fraud_flags else ""
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute(
                    "INSERT INTO verification_logs (payment_id, tx_ref, verification_status, gateway_response, amount_match, timestamp_valid, fraud_flags) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (payment_id, tx_ref, status, gateway_response[:500] if gateway_response else None, int(amount_match), int(timestamp_valid), flags_str),
                )
                conn.commit()
        else:
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

# Backward compatible aliases
create_subscription_level = create_subscription_plan
list_subscription_levels = list_subscription_plans
get_subscription_level = get_subscription_plan
list_predictions_for_level = list_predictions_for_plan

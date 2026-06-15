import sqlite3
from contextlib import closing
from pathlib import Path
import os
from config import USE_POSTGRES, DATABASE_URL, DB_PATH

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor

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
        time TEXT,
        home TEXT,
        away TEXT,
        prediction TEXT NOT NULL,
        admin_user_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(level_id) REFERENCES subscription_levels(id),
        FOREIGN KEY(admin_user_id) REFERENCES users(id)
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
    """
    CREATE TABLE IF NOT EXISTS admin_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(admin_user_id) REFERENCES users(id)
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
        time TEXT,
        home TEXT,
        away TEXT,
        prediction TEXT NOT NULL,
        admin_user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(level_id) REFERENCES subscription_levels(id),
        FOREIGN KEY(admin_user_id) REFERENCES users(id)
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
    """
    CREATE TABLE IF NOT EXISTS admin_audit_log (
        id SERIAL PRIMARY KEY,
        admin_user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(admin_user_id) REFERENCES users(id)
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
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                for stmt in SQL_CREATE_POSTGRES:
                    cur.execute(stmt)
            conn.commit()
        else:
            Path(DB_PATH.parent).mkdir(parents=True, exist_ok=True)
            for stmt in SQL_CREATE:
                conn.execute(stmt)
            conn.commit()

def create_user(telegram_id: int, name: str, email: str, phone: str, country_code: str):
    print(f"DEBUG create_user: telegram_id={telegram_id}, name={repr(name)}, email={repr(email)}, phone={repr(phone)}, country_code={repr(country_code)}")
    try:
        with closing(get_connection()) as conn:
            if USE_POSTGRES:
                with closing(conn.cursor()) as cur:
                    cur.execute(
                        "INSERT INTO users (telegram_id, name, email, phone, country_code) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (telegram_id) DO NOTHING RETURNING id",
                        (telegram_id, name.strip(), email.strip().lower(), phone.strip(), country_code.strip()),
                    )
                    result = cur.fetchone()
                    print(f"DEBUG create_user Postgres: result = {result}")
                    conn.commit()
            else:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO users (telegram_id, name, email, phone, country_code) VALUES (?, ?, ?, ?, ?)",
                    (telegram_id, name.strip(), email.strip().lower(), phone.strip(), country_code.strip()),
                )
                print(f"DEBUG create_user SQLite: lastrowid = {cur.lastrowid}")
                conn.commit()
        return get_user_by_telegram_id(telegram_id)
    except Exception as e:
        print(f"ERROR create_user: {e}", exc_info=True)
        raise

def get_user_by_telegram_id(telegram_id: int):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                return cur.fetchone()
        else:
            return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()

def get_user_by_id(user_id: int):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                return cur.fetchone()
        else:
            return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

def list_users():
    print("DEBUG: list_users() called")
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("SELECT * FROM users ORDER BY created_at DESC")
                users = cur.fetchall()
                print(f"DEBUG: Found {len(users)} users in Postgres")
                return users
        else:
            users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
            print(f"DEBUG: Found {len(users)} users in SQLite at {DB_PATH}")
            return users

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

def add_prediction(
    level_id: int,
    prediction: str,
    time: str = None,
    home: str = None,
    away: str = None,
    admin_user_id: int = None,
):
    print(f"DEBUG: add_prediction called with level_id={level_id}, time={time}, home={home}, away={away}, prediction={prediction!r}, admin_user_id={admin_user_id}")
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute(
                    """INSERT INTO predictions 
                       (level_id, time, home, away, prediction, admin_user_id) 
                       VALUES (%s, %s, %s, %s, %s, %s) 
                       RETURNING id""",
                    (
                        level_id,
                        time,
                        home,
                        away,
                        prediction.strip(),
                        admin_user_id,
                    ),
                )
                result = cur.fetchone()
                conn.commit()
                print(f"DEBUG: Postgres: inserted prediction with id={result}")
                return result['id']
        else:
            cur = conn.execute(
                """INSERT INTO predictions 
                   (level_id, time, home, away, prediction, admin_user_id) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    level_id,
                    time,
                    home,
                    away,
                    prediction.strip(),
                    admin_user_id,
                ),
            )
            conn.commit()
            print(f"DEBUG: SQLite: inserted prediction with id={cur.lastrowid}")
            return cur.lastrowid


def list_predictions(level_id: int = None):
    """List all predictions, optionally filtered by level_id. Backward-compatible with old schema."""
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                # Check column names
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'predictions'
                """)
                columns = [row[0] for row in cur.fetchall()]
                
                if level_id:
                    cur.execute(
                        """SELECT p.*, u.name as admin_name 
                           FROM predictions p 
                           LEFT JOIN users u ON p.admin_user_id = u.id 
                           WHERE p.level_id = %s 
                           ORDER BY p.created_at DESC""",
                        (level_id,),
                    )
                else:
                    cur.execute(
                        """SELECT p.*, u.name as admin_name 
                           FROM predictions p 
                           LEFT JOIN users u ON p.admin_user_id = u.id 
                           ORDER BY p.created_at DESC"""
                    )
                # Process rows to be backward-compatible
                rows = cur.fetchall()
                results = []
                for row in rows:
                    # Convert to dict
                    pred = dict(row)
                    # Backward compatibility
                    if 'prediction' not in pred or pred['prediction'] is None:
                        pred['prediction'] = (pred.get('title', '') + '\n\n' + pred.get('content', '')).strip() or None
                    if 'time' not in pred or pred['time'] is None:
                        pred['time'] = pred.get('game_date')
                    if 'home' not in pred or 'away' not in pred:
                        teams = pred.get('teams')
                        if teams and ' vs ' in teams:
                            home, away = teams.split(' vs ', 1)
                            pred['home'] = home.strip()
                            pred['away'] = away.strip()
                        else:
                            pred['home'] = None
                            pred['away'] = None
                    results.append(pred)
                return results
        else:
            # SQLite
            cursor = conn.execute("PRAGMA table_info(predictions)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if level_id:
                cursor = conn.execute(
                    """SELECT p.*, u.name as admin_name 
                       FROM predictions p 
                       LEFT JOIN users u ON p.admin_user_id = u.id 
                       WHERE p.level_id = ? 
                       ORDER BY p.created_at DESC""",
                    (level_id,),
                )
            else:
                cursor = conn.execute(
                    """SELECT p.*, u.name as admin_name 
                       FROM predictions p 
                       LEFT JOIN users u ON p.admin_user_id = u.id 
                       ORDER BY p.created_at DESC"""
                )
            # Process rows
            rows = cursor.fetchall()
            results = []
            for row in rows:
                pred = dict(row)
                # Backward compatibility
                if 'prediction' not in pred or pred['prediction'] is None:
                    pred['prediction'] = (pred.get('title', '') + '\n\n' + pred.get('content', '')).strip() or None
                if 'time' not in pred or pred['time'] is None:
                    pred['time'] = pred.get('game_date')
                if 'home' not in pred or 'away' not in pred:
                    teams = pred.get('teams')
                    if teams and ' vs ' in teams:
                        home, away = teams.split(' vs ', 1)
                        pred['home'] = home.strip()
                        pred['away'] = away.strip()
                    else:
                        pred['home'] = None
                        pred['away'] = None
                results.append(pred)
            return results


def list_predictions_for_plan(level_id: int):
    """List predictions for a plan. Backward-compatible."""
    return list_predictions(level_id)


def log_admin_action(admin_user_id: int, action: str, details: str = None):
    """Log an admin action to the audit log"""
    print(f"DEBUG: log_admin_action called with admin_user_id={admin_user_id}, action={action!r}, details={details!r}")
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute(
                    """INSERT INTO admin_audit_log (admin_user_id, action, details) 
                       VALUES (%s, %s, %s) 
                       RETURNING id""",
                    (admin_user_id, action, details),
                )
                conn.commit()
        else:
            conn.execute(
                """INSERT INTO admin_audit_log (admin_user_id, action, details) 
                   VALUES (?, ?, ?)""",
                (admin_user_id, action, details),
            )
            conn.commit()

def list_predictions_for_plan(level_id: int):
    with closing(get_connection()) as conn:
        if USE_POSTGRES:
            with closing(conn.cursor()) as cur:
                cur.execute("SELECT * FROM predictions WHERE level_id = %s ORDER BY created_at DESC", (level_id,))
                return cur.fetchall()
        else:
            return conn.execute("SELECT * FROM predictions WHERE level_id = ? ORDER BY created_at DESC", (level_id,)).fetchall()

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
            return conn.execute("SELECT * FROM payments WHERE status = 'PENDING' ORDER BY created_at ASC").fetchall()

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
    from datetime import datetime
    users = list_users()
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Telegram ID", "Name", "Email", "Phone", "Country Code", "Registered"])
        for user in users:
            created_at = user["created_at"]
            if isinstance(created_at, datetime):
                created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_at_str = str(created_at)
            writer.writerow([user["telegram_id"], user["name"], user["email"], user["phone"], user["country_code"], created_at_str])
    return path

# Backward compatible aliases
create_subscription_level = create_subscription_plan
list_subscription_levels = list_subscription_plans
get_subscription_level = get_subscription_plan
list_predictions_for_level = list_predictions_for_plan

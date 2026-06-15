import sqlite3
import config


def migrate_sqlite(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Step 1: Check if old columns exist
    cursor.execute("PRAGMA table_info(predictions)")
    columns = [col[1] for col in cursor.fetchall()]

    # Step 2: Add new columns if they don't exist
    new_columns = ['time', 'home', 'away', 'prediction']
    for col in new_columns:
        if col not in columns:
            print(f"Adding column: {col}")
            cursor.execute(f"ALTER TABLE predictions ADD COLUMN {col} TEXT")

    # Step 3: Backfill prediction from content/title for backward compatibility
    if 'content' in columns and 'title' in columns:
        print("Backfilling prediction from title and content...")
        cursor.execute("""
            UPDATE predictions 
            SET prediction = COALESCE(title || '\n\n' || content, title, content)
            WHERE prediction IS NULL OR prediction = ''
        """)

    # Step 4: Backfill time from game_date
    if 'game_date' in columns:
        print("Backfilling time from game_date...")
        cursor.execute("""
            UPDATE predictions 
            SET time = game_date
            WHERE time IS NULL OR time = ''
        """)

    # Step 5: Backfill teams into home/away if teams exists
    if 'teams' in columns:
        print("Backfilling teams into home/away...")
        cursor.execute("""
            SELECT id, teams FROM predictions 
            WHERE teams IS NOT NULL AND teams != '' AND (home IS NULL OR home = '' OR away IS NULL OR away = '')
        """)
        rows = cursor.fetchall()
        for pred_id, teams in rows:
            if ' vs ' in teams:
                home, away = teams.split(' vs ', 1)
                cursor.execute("""
                    UPDATE predictions 
                    SET home = ?, away = ?
                    WHERE id = ?
                """, (home.strip(), away.strip(), pred_id))

    conn.commit()
    conn.close()
    print("SQLite migration complete!")


def migrate_postgres(db_url):
    import psycopg2
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    # Step 1: Check if old columns exist
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'predictions'
    """)
    columns = [row[0] for row in cursor.fetchall()]

    # Step 2: Add new columns if they don't exist
    new_columns = ['time', 'home', 'away', 'prediction']
    for col in new_columns:
        if col not in columns:
            print(f"Adding column: {col}")
            cursor.execute(f"ALTER TABLE predictions ADD COLUMN {col} TEXT")

    # Step 3: Backfill prediction from content/title for backward compatibility
    if 'content' in columns and 'title' in columns:
        print("Backfilling prediction from title and content...")
        cursor.execute("""
            UPDATE predictions 
            SET prediction = COALESCE(title || '\n\n' || content, title, content)
            WHERE prediction IS NULL OR prediction = ''
        """)

    # Step 4: Backfill time from game_date
    if 'game_date' in columns:
        print("Backfilling time from game_date...")
        cursor.execute("""
            UPDATE predictions 
            SET time = game_date
            WHERE time IS NULL OR time = ''
        """)

    # Step 5: Backfill teams into home/away if teams exists
    if 'teams' in columns:
        print("Backfilling teams into home/away...")
        cursor.execute("""
            SELECT id, teams FROM predictions 
            WHERE teams IS NOT NULL AND teams != '' AND (home IS NULL OR home = '' OR away IS NULL OR away = '')
        """)
        rows = cursor.fetchall()
        for pred_id, teams in rows:
            if ' vs ' in teams:
                home, away = teams.split(' vs ', 1)
                cursor.execute("""
                    UPDATE predictions 
                    SET home = %s, away = %s
                    WHERE id = %s
                """, (home.strip(), away.strip(), pred_id))

    conn.commit()
    conn.close()
    print("Postgres migration complete!")


if __name__ == "__main__":
    if config.DATABASE_URL.startswith("postgres://") or config.DATABASE_URL.startswith("postgresql://"):
        migrate_postgres(config.DATABASE_URL)
    else:
        migrate_sqlite(config.DATABASE_PATH)

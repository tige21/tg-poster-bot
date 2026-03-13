import sqlite3
import os
from config import DB_PATH


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection = None) -> None:
    """Create all tables. If conn is provided, uses it (won't close). Otherwise creates and closes."""
    close_after = conn is None
    if conn is None:
        conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS proxies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            type        TEXT NOT NULL,
            host        TEXT NOT NULL,
            port        INTEGER NOT NULL,
            username    TEXT,
            password    TEXT,
            status      TEXT DEFAULT 'unchecked',
            ping_ms     INTEGER,
            checked_at  TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            phone           TEXT UNIQUE NOT NULL,
            session_string  TEXT,
            api_id          INTEGER NOT NULL,
            api_hash        TEXT NOT NULL,
            proxy_id        INTEGER REFERENCES proxies(id) ON DELETE SET NULL,
            status          TEXT DEFAULT 'active',
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier  TEXT UNIQUE NOT NULL,
            title       TEXT,
            telegram_id INTEGER,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS posts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            text        TEXT,
            image_path  TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id      INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            post_id         INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            group_ids       TEXT NOT NULL DEFAULT '[]',
            task_type       TEXT NOT NULL,
            schedule_type   TEXT NOT NULL,
            schedule_value  TEXT NOT NULL,
            delay_seconds   INTEGER DEFAULT 10,
            is_active       INTEGER DEFAULT 1,
            last_run_at     TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS autocomment_state (
            task_id         INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            group_id        INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            last_post_id    INTEGER,
            updated_at      TEXT,
            PRIMARY KEY (task_id, group_id)
        );

        CREATE TABLE IF NOT EXISTS send_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id     INTEGER,
            account_id  INTEGER,
            group_id    INTEGER,
            status      TEXT NOT NULL,
            error_text  TEXT,
            sent_at     TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    if close_after:
        conn.close()

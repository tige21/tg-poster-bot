import json
import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Proxies ───────────────────────────────────────────────────────────────────

def create_proxy(conn, *, type, host, port, username=None, password=None) -> int:
    cur = conn.execute(
        "INSERT INTO proxies (type, host, port, username, password) VALUES (?,?,?,?,?)",
        (type, host, port, username, password)
    )
    conn.commit()
    return cur.lastrowid


def get_proxy(conn, proxy_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM proxies WHERE id=?", (proxy_id,)).fetchone()
    return dict(row) if row else None


def list_proxies(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM proxies ORDER BY id").fetchall()]


def update_proxy_status(conn, proxy_id: int, status: str, ping_ms: int = None) -> None:
    conn.execute(
        "UPDATE proxies SET status=?, ping_ms=?, checked_at=? WHERE id=?",
        (status, ping_ms, _now(), proxy_id)
    )
    conn.commit()


def delete_proxy(conn, proxy_id: int) -> None:
    conn.execute("DELETE FROM proxies WHERE id=?", (proxy_id,))
    conn.commit()


# ── Accounts ──────────────────────────────────────────────────────────────────

def create_account(conn, *, phone, api_id, api_hash,
                   session_string=None, proxy_id=None) -> int:
    cur = conn.execute(
        "INSERT INTO accounts (phone, api_id, api_hash, session_string, proxy_id) "
        "VALUES (?,?,?,?,?)",
        (phone, api_id, api_hash, session_string, proxy_id)
    )
    conn.commit()
    return cur.lastrowid


def get_account(conn, account_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
    return dict(row) if row else None


def list_accounts(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()]


def update_account_status(conn, account_id: int, status: str) -> None:
    conn.execute("UPDATE accounts SET status=? WHERE id=?", (status, account_id))
    conn.commit()


def update_account_session(conn, account_id: int, session_string: str) -> None:
    conn.execute("UPDATE accounts SET session_string=? WHERE id=?",
                 (session_string, account_id))
    conn.commit()


# ── Groups ────────────────────────────────────────────────────────────────────

def create_group(conn, *, identifier, title=None, telegram_id=None) -> int:
    cur = conn.execute(
        "INSERT OR IGNORE INTO groups (identifier, title, telegram_id) VALUES (?,?,?)",
        (identifier, title, telegram_id)
    )
    conn.commit()
    if cur.lastrowid:
        return cur.lastrowid
    row = conn.execute("SELECT id FROM groups WHERE identifier=?",
                       (identifier,)).fetchone()
    if row is None:
        raise RuntimeError(f"create_group: could not find group after INSERT OR IGNORE for {identifier!r}")
    return row[0]


def get_group(conn, group_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM groups WHERE id=?", (group_id,)).fetchone()
    return dict(row) if row else None


def list_groups(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM groups ORDER BY id").fetchall()]


# ── Posts ─────────────────────────────────────────────────────────────────────

def create_post(conn, *, title, text=None, image_path=None) -> int:
    cur = conn.execute(
        "INSERT INTO posts (title, text, image_path) VALUES (?,?,?)",
        (title, text, image_path)
    )
    conn.commit()
    return cur.lastrowid


def get_post(conn, post_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    return dict(row) if row else None


def list_posts(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM posts ORDER BY id").fetchall()]


def delete_post(conn, post_id: int) -> None:
    conn.execute("DELETE FROM posts WHERE id=?", (post_id,))
    conn.commit()


# ── Tasks ─────────────────────────────────────────────────────────────────────

def create_task(conn, *, account_id, post_id, group_ids: list,
                task_type, schedule_type, schedule_value,
                delay_seconds=10) -> int:
    cur = conn.execute(
        "INSERT INTO tasks (account_id, post_id, group_ids, task_type, "
        "schedule_type, schedule_value, delay_seconds) VALUES (?,?,?,?,?,?,?)",
        (account_id, post_id, json.dumps(group_ids),
         task_type, schedule_type, schedule_value, delay_seconds)
    )
    conn.commit()
    return cur.lastrowid


def get_task(conn, task_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["group_ids"] = json.loads(d["group_ids"])
    return d


def list_tasks(conn, active_only=False) -> list[dict]:
    q = "SELECT * FROM tasks"
    if active_only:
        q += " WHERE is_active=1"
    rows = conn.execute(q + " ORDER BY id").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["group_ids"] = json.loads(d["group_ids"])
        result.append(d)
    return result


def update_task_active(conn, task_id: int, is_active: bool) -> None:
    conn.execute("UPDATE tasks SET is_active=? WHERE id=?",
                 (1 if is_active else 0, task_id))
    conn.commit()


def update_task_last_run(conn, task_id: int) -> None:
    conn.execute("UPDATE tasks SET last_run_at=? WHERE id=?", (_now(), task_id))
    conn.commit()


# ── Autocomment state ─────────────────────────────────────────────────────────

def upsert_autocomment_state(conn, task_id: int, group_id: int,
                              last_post_id: int) -> None:
    conn.execute(
        "INSERT INTO autocomment_state (task_id, group_id, last_post_id, updated_at) "
        "VALUES (?,?,?,?) ON CONFLICT(task_id, group_id) DO UPDATE SET "
        "last_post_id=excluded.last_post_id, updated_at=excluded.updated_at",
        (task_id, group_id, last_post_id, _now())
    )
    conn.commit()


def get_autocomment_state(conn, task_id: int, group_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM autocomment_state WHERE task_id=? AND group_id=?",
        (task_id, group_id)
    ).fetchone()
    return dict(row) if row else None


# ── Send log ──────────────────────────────────────────────────────────────────

def log_send(conn, *, task_id, account_id, group_id,
             status, error_text=None) -> None:
    conn.execute(
        "INSERT INTO send_log (task_id, account_id, group_id, status, error_text) "
        "VALUES (?,?,?,?,?)",
        (task_id, account_id, group_id, status, error_text)
    )
    conn.commit()

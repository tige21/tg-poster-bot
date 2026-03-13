import os
import sqlite3
import pytest

os.environ.setdefault("BOT_TOKEN", "x")
os.environ.setdefault("ADMIN_CHAT_ID", "1")
os.environ.setdefault("API_ID", "1")
os.environ.setdefault("API_HASH", "x")
os.environ.setdefault("DB_PATH", ":memory:")

import config
config.DB_PATH = ":memory:"

import db.database as db_mod
db_mod.DB_PATH = ":memory:"

from db.database import init_db, get_conn


@pytest.fixture
def conn(monkeypatch):
    """Use a single in-memory connection for the whole test."""
    import sqlite3
    import db.database as db_mod

    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    monkeypatch.setattr(db_mod, "get_conn", lambda: c)
    init_db(c)
    return c


def test_init_db_creates_tables(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert {"accounts", "proxies", "groups", "posts", "tasks",
            "autocomment_state", "send_log"} <= tables


def test_init_db_idempotent():
    init_db()
    init_db()


from db.models import (
    create_proxy, get_proxy, list_proxies, update_proxy_status, delete_proxy,
    create_account, get_account, list_accounts, update_account_status,
    create_group, get_group, list_groups,
    create_post, get_post, list_posts, delete_post,
    create_task, get_task, list_tasks, update_task_active,
    log_send, upsert_autocomment_state, get_autocomment_state,
)


def test_proxy_crud(conn):
    pid = create_proxy(conn, type="socks5", host="1.2.3.4", port=1080,
                       username="u", password="p")
    assert pid > 0
    p = get_proxy(conn, pid)
    assert p["host"] == "1.2.3.4"
    assert p["status"] == "unchecked"
    update_proxy_status(conn, pid, "ok", ping_ms=120)
    assert get_proxy(conn, pid)["status"] == "ok"
    assert len(list_proxies(conn)) == 1
    delete_proxy(conn, pid)
    assert get_proxy(conn, pid) is None


def test_account_crud(conn):
    pid = create_proxy(conn, type="socks5", host="1.2.3.4", port=1080)
    aid = create_account(conn, phone="+79001234567", api_id=111,
                         api_hash="abc", proxy_id=pid)
    assert aid > 0
    a = get_account(conn, aid)
    assert a["phone"] == "+79001234567"
    assert a["status"] == "active"
    update_account_status(conn, aid, "banned")
    assert get_account(conn, aid)["status"] == "banned"


def test_post_crud(conn):
    pid = create_post(conn, title="Test Post", text="Hello world")
    assert pid > 0
    p = get_post(conn, pid)
    assert p["title"] == "Test Post"
    assert len(list_posts(conn)) == 1
    delete_post(conn, pid)
    assert get_post(conn, pid) is None


def test_task_crud(conn):
    create_proxy(conn, type="socks5", host="1.2.3.4", port=1080)
    acc_id = create_account(conn, phone="+79001234567", api_id=111, api_hash="abc")
    post_id = create_post(conn, title="P", text="text")
    group_id = create_group(conn, identifier="@testgroup", title="Test")
    tid = create_task(conn, account_id=acc_id, post_id=post_id,
                      group_ids=[group_id], task_type="post",
                      schedule_type="daily", schedule_value="09:00")
    assert tid > 0
    t = get_task(conn, tid)
    assert t["task_type"] == "post"
    assert t["is_active"] == 1
    update_task_active(conn, tid, False)
    assert get_task(conn, tid)["is_active"] == 0


def test_autocomment_state(conn):
    create_proxy(conn, type="socks5", host="1.2.3.4", port=1080)
    acc_id = create_account(conn, phone="+79001234567", api_id=111, api_hash="abc")
    post_id = create_post(conn, title="P", text="text")
    group_id = create_group(conn, identifier="@testgroup", title="Test")
    task_id = create_task(conn, account_id=acc_id, post_id=post_id,
                          group_ids=[group_id], task_type="autocomment",
                          schedule_type="interval", schedule_value="30")
    upsert_autocomment_state(conn, task_id, group_id, last_post_id=9999)
    state = get_autocomment_state(conn, task_id, group_id)
    assert state["last_post_id"] == 9999
    upsert_autocomment_state(conn, task_id, group_id, last_post_id=10001)
    assert get_autocomment_state(conn, task_id, group_id)["last_post_id"] == 10001


def test_send_log(conn):
    log_send(conn, task_id=1, account_id=1, group_id=1, status="ok")
    log_send(conn, task_id=1, account_id=1, group_id=1,
             status="error", error_text="flood")

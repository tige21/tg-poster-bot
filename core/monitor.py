import asyncio
import logging
import random
from telethon import events
from db.models import (
    list_tasks, get_post, get_account, get_group,
    upsert_autocomment_state, get_autocomment_state, log_send,
    update_account_status,
)
from core.poster import send_comment

logger = logging.getLogger(__name__)

_monitor_tasks: dict[int, asyncio.Task] = {}  # task_id → asyncio.Task


async def _run_monitor(pool, conn, task: dict) -> None:
    """Monitor groups for new posts and auto-comment."""
    client = pool.get_client(task["account_id"])
    if not client:
        logger.warning(f"No client for account {task['account_id']}")
        return

    post = get_post(conn, task["post_id"])
    if not post:
        return

    group_ids_db = task["group_ids"]  # list of DB group IDs
    # Resolve @username/invite → numeric telegram_id, cache in DB
    tg_ids = {}
    for gid in group_ids_db:
        g = get_group(conn, gid)
        if not g:
            continue
        tg_id = g.get("telegram_id")
        if not tg_id:
            try:
                entity = await client.get_entity(g["identifier"])
                tg_id = entity.id
                conn.execute("UPDATE groups SET telegram_id=? WHERE id=?", (tg_id, gid))
                conn.commit()
                logger.info(f"Resolved {g['identifier']} → {tg_id}")
            except Exception as e:
                logger.warning(f"Can't resolve group {g['identifier']}: {e}")
                continue
        tg_ids[tg_id] = gid

    if not tg_ids:
        logger.warning(f"Monitor task {task['id']}: no resolvable groups, aborting")
        return

    @client.on(events.NewMessage(chats=list(tg_ids.keys())))
    async def handler(event):
        tg_group_id = event.chat_id
        db_group_id = tg_ids.get(tg_group_id)
        if db_group_id is None:
            return

        delay = random.randint(5, max(5, task["delay_seconds"]))
        await asyncio.sleep(delay)

        try:
            from telethon.errors import FloodWaitError
            await send_comment(client, event.message, post)
            log_send(conn, task_id=task["id"], account_id=task["account_id"],
                     group_id=db_group_id, status="ok")
            upsert_autocomment_state(conn, task["id"], db_group_id,
                                     last_post_id=event.message.id)
        except FloodWaitError as e:
            logger.warning(f"FloodWait {e.seconds}s on task {task['id']}")
            log_send(conn, task_id=task["id"], account_id=task["account_id"],
                     group_id=db_group_id, status="flood_wait",
                     error_text=str(e.seconds))
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error in autocomment task {task['id']}: {e}")
            log_send(conn, task_id=task["id"], account_id=task["account_id"],
                     group_id=db_group_id, status="error", error_text=str(e))

    # Wait until cancelled — don't call run_until_disconnected() as client is shared
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        client.remove_event_handler(handler)
        raise


def start_monitor(pool, conn, task: dict) -> None:
    """Start autocomment monitor for a task (non-blocking)."""
    task_id = task["id"]
    if task_id in _monitor_tasks and not _monitor_tasks[task_id].done():
        return  # already running
    t = asyncio.create_task(_run_monitor(pool, conn, task))
    _monitor_tasks[task_id] = t
    logger.info(f"Monitor started for task {task_id}")


def stop_monitor(task_id: int) -> None:
    """Cancel autocomment monitor for a task."""
    t = _monitor_tasks.pop(task_id, None)
    if t and not t.done():
        t.cancel()


def start_all_monitors(pool, conn) -> None:
    """Start monitors for all active autocomment tasks."""
    for task in list_tasks(conn, active_only=True):
        if task["task_type"] == "autocomment":
            start_monitor(pool, conn, task)

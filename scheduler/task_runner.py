import asyncio
import logging
import random
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from telethon.errors import FloodWaitError
from core.poster import send_post
from db.models import (
    list_tasks, get_post, get_account, get_proxy, get_group,
    log_send, update_task_last_run, update_account_status,
)

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def build_trigger(schedule_type: str, schedule_value: str):
    if schedule_type == "daily":
        h, m = schedule_value.split(":")
        return CronTrigger(hour=int(h), minute=int(m))
    elif schedule_type == "interval":
        return IntervalTrigger(minutes=int(schedule_value))
    elif schedule_type == "once":
        return DateTrigger(run_date=datetime.fromisoformat(schedule_value))
    else:
        raise ValueError(f"Unknown schedule_type: {schedule_type!r}")


def parse_schedule(schedule_type: str, schedule_value: str):
    """Alias kept for backwards compat."""
    return build_trigger(schedule_type, schedule_value)


async def _run_post_task(pool, conn, task_id: int) -> None:
    """Execute one posting task: send post to all groups with random delays."""
    from db.models import get_task
    task = get_task(conn, task_id)
    if not task or not task["is_active"]:
        return

    client = pool.get_client(task["account_id"])
    if not client:
        logger.warning(f"No client for task {task_id}, account {task['account_id']}")
        return

    post = get_post(conn, task["post_id"])
    if not post:
        return

    for db_group_id in task["group_ids"]:
        group = get_group(conn, db_group_id)
        if not group:
            continue
        # Use numeric telegram_id if resolved, else fall back to @username/invite
        tg_id = group.get("telegram_id") or group["identifier"]
        delay = random.randint(5, max(5, task["delay_seconds"]))
        await asyncio.sleep(delay)
        try:
            await send_post(client, tg_id, post)
            log_send(conn, task_id=task_id, account_id=task["account_id"],
                     group_id=db_group_id, status="ok")
        except FloodWaitError as e:
            logger.warning(f"FloodWait {e.seconds}s on task {task_id}")
            log_send(conn, task_id=task_id, account_id=task["account_id"],
                     group_id=db_group_id, status="flood_wait",
                     error_text=str(e.seconds))
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error posting task {task_id} → group {db_group_id}: {e}")
            log_send(conn, task_id=task_id, account_id=task["account_id"],
                     group_id=db_group_id, status="error", error_text=str(e))

    update_task_last_run(conn, task_id)


def register_task(pool, conn, task: dict) -> None:
    """Add a task to the scheduler."""
    if task["task_type"] != "post":
        return  # autocomment tasks are handled by monitor.py
    job_id = f"task_{task['id']}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    trigger = build_trigger(task["schedule_type"], task["schedule_value"])
    scheduler.add_job(
        _run_post_task,
        trigger=trigger,
        id=job_id,
        args=[pool, conn, task["id"]],
        replace_existing=True,
    )
    logger.info(f"Registered scheduler job {job_id}")


def unregister_task(task_id: int) -> None:
    job_id = f"task_{task_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def register_all_tasks(pool, conn) -> None:
    """Register all active post tasks at startup."""
    for task in list_tasks(conn, active_only=True):
        register_task(pool, conn, task)

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
from db.database import db_conn
from db.models import (
    list_tasks, get_task, get_post, get_group,
    log_send, update_task_last_run, update_task_active,
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


async def _run_post_task(pool, task_id: int) -> None:
    """Execute one posting task: send post to all groups with random delays.
    Opens its own DB connection per execution to avoid concurrent-access issues.
    """
    with db_conn() as conn:
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

        groups = [(db_gid, get_group(conn, db_gid)) for db_gid in task["group_ids"]]

    for db_group_id, group in groups:
        if not group:
            continue
        tg_id = group.get("telegram_id") or group["identifier"]
        delay = random.randint(5, max(6, task["delay_seconds"]))
        await asyncio.sleep(delay)
        try:
            await send_post(client, tg_id, post)
            with db_conn() as conn:
                log_send(conn, task_id=task_id, account_id=task["account_id"],
                         group_id=db_group_id, status="ok")
        except FloodWaitError as e:
            # Scenario 11 fix: skip remaining groups, don't block event loop
            logger.warning(f"FloodWait {e.seconds}s on account {task['account_id']}, stopping task {task_id} early")
            with db_conn() as conn:
                log_send(conn, task_id=task_id, account_id=task["account_id"],
                         group_id=db_group_id, status="flood_wait",
                         error_text=str(e.seconds))
            break  # stop posting to other groups; scheduler will retry next interval
        except Exception as e:
            logger.error(f"Error posting task {task_id} → group {db_group_id}: {e}")
            with db_conn() as conn:
                log_send(conn, task_id=task_id, account_id=task["account_id"],
                         group_id=db_group_id, status="error", error_text=str(e))

    with db_conn() as conn:
        update_task_last_run(conn, task_id)
        # Scenarios 2/8 fix: auto-deactivate one-shot tasks after they fire
        task_fresh = get_task(conn, task_id)
        if task_fresh and task_fresh["schedule_type"] == "once":
            update_task_active(conn, task_id, False)
            logger.info(f"Task {task_id} (once) auto-deactivated after execution")


def register_task(pool, task: dict) -> None:
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
        args=[pool, task["id"]],
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
        register_task(pool, task)

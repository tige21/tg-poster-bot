import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_CHAT_ID, MEDIA_DIR
from db.database import init_db, get_conn
from core.account_pool import AccountPool
from core.monitor import start_all_monitors
from scheduler.task_runner import register_all_tasks, scheduler as _scheduler
from bot.router import main_router
from bot.handlers import proxies, accounts, groups, posts, tasks

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main():
    # Dirs
    os.makedirs(MEDIA_DIR, exist_ok=True)

    # DB
    init_db()
    conn = get_conn()

    # Telethon pool
    pool = AccountPool()
    await pool.start_all(conn)

    # Wire pool reference into handlers
    accounts._pool_ref = pool
    groups._pool_ref = pool
    tasks._pool_ref = pool
    tasks._conn_ref = conn

    # Scheduler
    _scheduler.start()
    register_all_tasks(pool, conn)

    # Auto-comment monitors
    start_all_monitors(pool, conn)

    # Aiogram
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(main_router)
    dp.include_router(proxies.router)
    dp.include_router(accounts.router)
    dp.include_router(groups.router)
    dp.include_router(posts.router)
    dp.include_router(tasks.router)

    logger.info(f"Bot started. Admin: {ADMIN_CHAT_ID}")
    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        await pool.stop_all()
        _scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

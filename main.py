import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import Filter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from config import BOT_TOKEN, ADMIN_CHAT_ID, MEDIA_DIR
from db.database import init_db, db_conn
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


class AdminOnly(Filter):
    """Aiogram filter: only ADMIN_CHAT_ID passes."""
    async def __call__(self, message: Message) -> bool:
        return message.chat.id == ADMIN_CHAT_ID


async def main():
    # Dirs
    os.makedirs(MEDIA_DIR, exist_ok=True)

    # DB init
    init_db()

    # Telethon pool — uses its own short-lived connection
    pool = AccountPool()
    with db_conn() as conn:
        await pool.start_all(conn)

    # Wire pool reference into handlers
    accounts._pool_ref = pool
    groups._pool_ref = pool
    tasks._pool_ref = pool


    # Scheduler — jobs open their own DB connections per execution
    _scheduler.start()
    with db_conn() as conn:
        register_all_tasks(pool, conn)
        start_all_monitors(pool, conn)

    # Aiogram
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Apply admin filter to all routers globally
    for router in [main_router, proxies.router, accounts.router,
                   groups.router, posts.router, tasks.router]:
        router.message.filter(AdminOnly())
        dp.include_router(router)

    logger.info(f"Bot started. Admin: {ADMIN_CHAT_ID}")
    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        await pool.stop_all()
        _scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

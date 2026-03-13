from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from config import ADMIN_CHAT_ID

main_router = Router()


def admin_only(func):
    """Decorator: only ADMIN_CHAT_ID can use these commands."""
    async def wrapper(message: Message, *args, **kwargs):
        if message.chat.id != ADMIN_CHAT_ID:
            return
        return await func(message, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


@main_router.message(Command("start"))
async def cmd_start(message: Message):
    if message.chat.id != ADMIN_CHAT_ID:
        return
    await message.answer(
        "🤖 <b>Poster Bot</b>\n\n"
        "Команды:\n"
        "/accounts — управление аккаунтами\n"
        "/proxies — управление прокси\n"
        "/groups — управление группами\n"
        "/posts — библиотека постов\n"
        "/tasks — задачи рассылки",
        parse_mode="HTML"
    )

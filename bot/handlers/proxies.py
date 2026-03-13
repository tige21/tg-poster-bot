import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from db.database import get_conn
from db.models import create_proxy, list_proxies, get_proxy, delete_proxy, update_proxy_status
from core.proxy_checker import check_proxy

router = Router()


class AddProxy(StatesGroup):
    waiting_for_data = State()


@router.message(Command("proxies"))
async def cmd_proxies(message: Message):
    conn = get_conn()
    proxies = list_proxies(conn)
    if not proxies:
        await message.answer("Прокси не добавлены. /add_proxy — добавить.")
        return
    lines = ["📡 <b>Прокси:</b>\n"]
    for p in proxies:
        icon = {"ok": "✅", "slow": "🟡", "fail": "❌", "unchecked": "⬜"}.get(p["status"], "⬜")
        ping = f" {p['ping_ms']}ms" if p.get("ping_ms") else ""
        lines.append(f"{icon} #{p['id']} {p['type'].upper()} {p['host']}:{p['port']}{ping}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("add_proxy"))
async def cmd_add_proxy(message: Message, state: FSMContext):
    await state.set_state(AddProxy.waiting_for_data)
    await message.answer(
        "Введи прокси в формате:\n"
        "<code>socks5 host port [username password]</code>\n\n"
        "Пример: <code>socks5 1.2.3.4 1080 user pass</code>",
        parse_mode="HTML"
    )


@router.message(AddProxy.waiting_for_data)
async def process_proxy_data(message: Message, state: FSMContext):
    await state.clear()
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.answer("❌ Неверный формат. Попробуй ещё раз: /add_proxy")
        return
    proxy_type = parts[0].lower()
    host = parts[1]
    try:
        port = int(parts[2])
    except ValueError:
        await message.answer("❌ Порт должен быть числом.")
        return
    username = parts[3] if len(parts) > 3 else None
    password = parts[4] if len(parts) > 4 else None

    await message.answer("⏳ Проверяю прокси...")
    result = await check_proxy(type=proxy_type, host=host, port=port,
                               username=username, password=password)
    conn = get_conn()
    pid = create_proxy(conn, type=proxy_type, host=host, port=port,
                       username=username, password=password)
    update_proxy_status(conn, pid, result["status"], ping_ms=result.get("ping_ms"))

    icon = {"ok": "✅", "slow": "🟡", "fail": "❌"}.get(result["status"], "⬜")
    ping = f", {result['ping_ms']}ms" if result.get("ping_ms") else ""
    await message.answer(
        f"{icon} Прокси #{pid} добавлен: {result['status'].upper()}{ping}\n"
        f"{proxy_type.upper()} {host}:{port}"
    )


@router.message(Command("del_proxy"))
async def cmd_del_proxy(message: Message):
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("Использование: /del_proxy <id>")
        return
    try:
        pid = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    conn = get_conn()
    if not get_proxy(conn, pid):
        await message.answer(f"❌ Прокси #{pid} не найден.")
        return
    delete_proxy(conn, pid)
    await message.answer(f"✅ Прокси #{pid} удалён.")

import asyncio
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from telethon import TelegramClient
from telethon.sessions import StringSession
from db.database import db_conn
from db.models import (
    create_account, list_accounts, get_account,
    update_account_status, update_account_session, list_proxies,
)
from config import API_ID, API_HASH

router = Router()

# Temporary storage for in-progress auth clients
_pending_clients: dict[int, TelegramClient] = {}  # chat_id → client
# Set by main.py after pool is created
_pool_ref = None


class AddAccount(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()  # 2FA


@router.message(Command("accounts"))
async def cmd_accounts(message: Message):
    with db_conn() as conn:
        accounts = list_accounts(conn)
    if not accounts:
        await message.answer("Аккаунты не добавлены. /add_account — добавить.")
        return
    lines = ["👤 <b>Аккаунты:</b>\n"]
    for a in accounts:
        icon = {"active": "✅", "needs_relogin": "🔄", "banned": "❌"}.get(a["status"], "⬜")
        proxy = f" → прокси #{a['proxy_id']}" if a.get("proxy_id") else ""
        lines.append(f"{icon} #{a['id']} {a['phone']}{proxy}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("add_account"))
async def cmd_add_account(message: Message, state: FSMContext):
    await state.set_state(AddAccount.waiting_phone)
    await message.answer("Введи номер телефона в формате <code>+79991234567</code>:",
                         parse_mode="HTML")


@router.message(AddAccount.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("❌ Формат: +79991234567")
        return

    await message.answer("⏳ Отправляю код...")
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        result = await client.send_code_request(phone)
    except Exception as e:
        await client.disconnect()
        await message.answer(f"❌ Ошибка: {e}")
        await state.clear()
        return

    _pending_clients[message.chat.id] = client
    await state.update_data(phone=phone, phone_code_hash=result.phone_code_hash)
    await state.set_state(AddAccount.waiting_code)
    await message.answer("📲 Код отправлен. Введи его:")


@router.message(AddAccount.waiting_code)
async def process_code(message: Message, state: FSMContext):
    code = message.text.strip()
    data = await state.get_data()
    phone = data["phone"]
    client = _pending_clients.get(message.chat.id)
    if not client:
        await message.answer("❌ Сессия истекла. Начни заново: /add_account")
        await state.clear()
        return

    try:
        await client.sign_in(phone=phone, code=code,
                             phone_code_hash=data["phone_code_hash"])
    except Exception as e:
        if "password" in str(e).lower() or "2fa" in str(e).lower():
            await state.set_state(AddAccount.waiting_password)
            await message.answer("🔐 Требуется пароль двухфакторной аутентификации:")
            return
        await client.disconnect()
        _pending_clients.pop(message.chat.id, None)
        await message.answer(f"❌ Ошибка входа: {e}")
        await state.clear()
        return

    await _save_account(message, state, client, phone)


@router.message(AddAccount.waiting_password)
async def process_password(message: Message, state: FSMContext):
    data = await state.get_data()
    phone = data["phone"]
    client = _pending_clients.get(message.chat.id)
    if not client:
        await message.answer("❌ Сессия истекла. Начни заново: /add_account")
        await state.clear()
        return
    try:
        await client.sign_in(password=message.text.strip())
    except Exception as e:
        await client.disconnect()
        _pending_clients.pop(message.chat.id, None)
        await message.answer(f"❌ Неверный пароль: {e}")
        await state.clear()
        return
    await _save_account(message, state, client, phone)


async def _save_account(message: Message, state: FSMContext,
                        client: TelegramClient, phone: str):
    session_string = client.session.save()
    with db_conn() as conn:
        acc_id = create_account(conn, phone=phone, api_id=API_ID,
                                api_hash=API_HASH, session_string=session_string)
        has_proxies = bool(list_proxies(conn))

    _pending_clients.pop(message.chat.id, None)
    await state.clear()

    proxy_hint = " Привязать прокси: /set_proxy" if has_proxies else ""
    await message.answer(f"✅ Аккаунт #{acc_id} ({phone}) добавлен!{proxy_hint}")

    if _pool_ref:
        await _pool_ref.add(acc_id, session_string, API_ID, API_HASH)


@router.message(Command("set_proxy"))
async def cmd_set_proxy(message: Message):
    """Usage: /set_proxy <account_id> <proxy_id>"""
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.answer("Использование: /set_proxy <account_id> <proxy_id>")
        return
    try:
        acc_id, proxy_id = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("❌ ID должны быть числами.")
        return
    with db_conn() as conn:
        conn.execute("UPDATE accounts SET proxy_id=? WHERE id=?", (proxy_id, acc_id))
        conn.commit()
    await message.answer(f"✅ Прокси #{proxy_id} привязан к аккаунту #{acc_id}.")

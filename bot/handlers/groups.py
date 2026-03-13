from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from db.database import get_conn
from db.models import create_group, list_groups

router = Router()


class AddGroup(StatesGroup):
    waiting_identifier = State()


@router.message(Command("groups"))
async def cmd_groups(message: Message):
    conn = get_conn()
    groups = list_groups(conn)
    if not groups:
        await message.answer("Группы не добавлены. /add_group — добавить.")
        return
    lines = ["👥 <b>Группы:</b>\n"]
    for g in groups:
        lines.append(f"#{g['id']} {g['title'] or g['identifier']}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("add_group"))
async def cmd_add_group(message: Message, state: FSMContext):
    await state.set_state(AddGroup.waiting_identifier)
    await message.answer("Введи @username или invite-ссылку группы/канала:")


@router.message(AddGroup.waiting_identifier)
async def process_group(message: Message, state: FSMContext):
    identifier = message.text.strip()
    await state.clear()
    conn = get_conn()
    gid = create_group(conn, identifier=identifier)
    await message.answer(f"✅ Группа #{gid} добавлена: {identifier}")

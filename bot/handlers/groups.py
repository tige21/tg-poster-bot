from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from db.database import db_conn
from db.models import create_group, list_groups

router = Router()
# Set by main.py
_pool_ref = None


class AddGroup(StatesGroup):
    waiting_identifier = State()


@router.message(Command("groups"))
async def cmd_groups(message: Message):
    with db_conn() as conn:
        groups = list_groups(conn)
    if not groups:
        await message.answer("Группы не добавлены. /add_group — добавить.")
        return
    lines = ["👥 <b>Группы:</b>\n"]
    for g in groups:
        tg = f" (tg_id: {g['telegram_id']})" if g.get("telegram_id") else " (не разрешён)"
        lines.append(f"#{g['id']} {g['title'] or g['identifier']}{tg}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("add_group"))
async def cmd_add_group(message: Message, state: FSMContext):
    await state.set_state(AddGroup.waiting_identifier)
    await message.answer("Введи @username или invite-ссылку группы/канала:")


@router.message(AddGroup.waiting_identifier)
async def process_group(message: Message, state: FSMContext):
    identifier = message.text.strip()
    await state.clear()
    with db_conn() as conn:
        gid = create_group(conn, identifier=identifier)

    # Try to resolve telegram_id using any connected account
    tg_id = None
    if _pool_ref:
        ids = _pool_ref.list_ids()
        if ids:
            client = _pool_ref.get_client(ids[0])
            try:
                entity = await client.get_entity(identifier)
                tg_id = entity.id
                with db_conn() as conn:
                    conn.execute("UPDATE groups SET telegram_id=?, title=? WHERE id=?",
                                 (tg_id, getattr(entity, "title", None) or identifier, gid))
                    conn.commit()
            except Exception as e:
                pass  # Will be resolved later when monitor starts

    if tg_id:
        await message.answer(f"✅ Группа #{gid} добавлена и разрешена: {identifier} (ID: {tg_id})")
    else:
        await message.answer(
            f"✅ Группа #{gid} добавлена: {identifier}\n"
            f"⚠️ telegram_id не разрешён — будет резолвиться при первом запуске задачи."
        )

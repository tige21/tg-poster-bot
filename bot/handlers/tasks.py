from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from db.database import db_conn
from db.models import (
    create_task, list_tasks, get_task, update_task_active,
    list_accounts, get_account, list_posts, list_groups,
)

router = Router()

# Set by main.py
_pool_ref = None


class AddTask(StatesGroup):
    waiting_account = State()
    waiting_post = State()
    waiting_groups = State()
    waiting_type = State()
    waiting_schedule = State()


@router.message(Command("tasks"))
async def cmd_tasks(message: Message):
    with db_conn() as conn:
        tasks = list_tasks(conn)
    if not tasks:
        await message.answer("Задач нет. /add_task — создать.")
        return
    lines = ["📋 <b>Задачи:</b>\n"]
    for t in tasks:
        status = "✅" if t["is_active"] else "⏸"
        lines.append(
            f"{status} #{t['id']} [{t['task_type']}] "
            f"acc#{t['account_id']} post#{t['post_id']} "
            f"({t['schedule_type']}:{t['schedule_value']})"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("add_task"))
async def cmd_add_task(message: Message, state: FSMContext):
    with db_conn() as conn:
        accounts = list_accounts(conn)
    if not accounts:
        await message.answer("❌ Сначала добавь аккаунт: /add_account")
        return
    lines = ["Выбери аккаунт (введи номер ID):"]
    for a in accounts:
        lines.append(f"  #{a['id']} {a['phone']}")
    await state.set_state(AddTask.waiting_account)
    await message.answer("\n".join(lines))


@router.message(AddTask.waiting_account)
async def process_account(message: Message, state: FSMContext):
    try:
        acc_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи числовой ID.")
        return
    with db_conn() as conn:
        # Scenario 4 fix: validate account exists before proceeding
        if not get_account(conn, acc_id):
            await message.answer(f"❌ Аккаунт #{acc_id} не найден. Введи ID из списка выше.")
            return
        posts = list_posts(conn)
    if not posts:
        await message.answer("❌ Сначала создай пост: /add_post")
        await state.clear()
        return
    await state.update_data(account_id=acc_id)
    lines = ["Выбери пост (введи ID):"]
    for p in posts:
        lines.append(f"  #{p['id']} {p['title']}")
    await state.set_state(AddTask.waiting_post)
    await message.answer("\n".join(lines))


@router.message(AddTask.waiting_post)
async def process_post(message: Message, state: FSMContext):
    try:
        post_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи числовой ID.")
        return
    with db_conn() as conn:
        groups = list_groups(conn)
    if not groups:
        await message.answer("❌ Сначала добавь группы: /add_group")
        await state.clear()
        return
    await state.update_data(post_id=post_id)
    lines = ["Введи ID групп через запятую:"]
    for g in groups:
        lines.append(f"  #{g['id']} {g['title'] or g['identifier']}")
    await state.set_state(AddTask.waiting_groups)
    await message.answer("\n".join(lines))


@router.message(AddTask.waiting_groups)
async def process_groups(message: Message, state: FSMContext):
    try:
        group_ids = [int(x.strip()) for x in message.text.split(",")]
    except ValueError:
        await message.answer("❌ Введи ID через запятую: 1,2,3")
        return
    await state.update_data(group_ids=group_ids)
    await state.set_state(AddTask.waiting_type)
    await message.answer(
        "Тип задачи:\n"
        "  <code>post</code> — публиковать посты по расписанию\n"
        "  <code>autocomment</code> — комментировать новые посты",
        parse_mode="HTML"
    )


@router.message(AddTask.waiting_type)
async def process_type(message: Message, state: FSMContext):
    task_type = message.text.strip().lower()
    if task_type not in ("post", "autocomment"):
        await message.answer("❌ Введи: post или autocomment")
        return
    await state.update_data(task_type=task_type)
    await state.set_state(AddTask.waiting_schedule)
    await message.answer(
        "Расписание:\n"
        "  <code>daily HH:MM</code> — каждый день в указанное время\n"
        "  <code>interval N</code> — каждые N минут\n"
        "  <code>once YYYY-MM-DDTHH:MM</code> — один раз",
        parse_mode="HTML"
    )


@router.message(AddTask.waiting_schedule)
async def process_schedule(message: Message, state: FSMContext):
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Формат: daily 14:00 или interval 30 или once 2026-06-01T10:00")
        return
    schedule_type, schedule_value = parts[0].lower(), parts[1]
    if schedule_type not in ("daily", "interval", "once"):
        await message.answer("❌ Тип: daily, interval или once")
        return

    # Validate schedule_value before persisting
    from scheduler.task_runner import build_trigger
    from datetime import datetime, timezone
    try:
        build_trigger(schedule_type, schedule_value)
    except Exception:
        await message.answer(
            "❌ Неверный формат значения расписания.\n"
            "Примеры: <code>daily 14:30</code> | <code>interval 30</code> | "
            "<code>once 2026-06-01T10:00</code>",
            parse_mode="HTML"
        )
        return
    # Scenarios 2/8 fix: reject past datetimes for "once" tasks
    if schedule_type == "once":
        run_at = datetime.fromisoformat(schedule_value)
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
        if run_at <= datetime.now(timezone.utc):
            await message.answer("❌ Время для once-задачи должно быть в будущем.")
            return

    data = await state.get_data()
    await state.clear()

    # Scenario 7 fix: warn if autocomment task already exists for same account+groups
    if data["task_type"] == "autocomment":
        with db_conn() as conn:
            existing = [
                t for t in list_tasks(conn, active_only=True)
                if t["task_type"] == "autocomment"
                and t["account_id"] == data["account_id"]
                and set(t["group_ids"]) & set(data["group_ids"])
            ]
        if existing:
            overlap = ", ".join(f"#{t['id']}" for t in existing)
            await message.answer(
                f"⚠️ Уже есть активные autocomment-задачи ({overlap}) на этом аккаунте "
                f"с пересекающимися группами. Два хендлера на одну группу приведут к двойным комментариям."
            )

    import sqlite3
    try:
        with db_conn() as conn:
            task_id = create_task(
                conn,
                account_id=data["account_id"],
                post_id=data["post_id"],
                group_ids=data["group_ids"],
                task_type=data["task_type"],
                schedule_type=schedule_type,
                schedule_value=schedule_value,
            )
            task = get_task(conn, task_id)
    except sqlite3.IntegrityError as e:
        await message.answer(f"❌ Ошибка создания задачи: неверный аккаунт или пост (FK). {e}")
        return

    # Register in scheduler / monitor
    if _pool_ref:
        if data["task_type"] == "post":
            from scheduler.task_runner import register_task
            register_task(_pool_ref, task)
        else:
            from core.monitor import start_monitor
            start_monitor(_pool_ref, task)

    await message.answer(
        f"✅ Задача #{task_id} создана:\n"
        f"  Тип: {data['task_type']}\n"
        f"  Расписание: {schedule_type} {schedule_value}"
    )


@router.message(Command("toggle_task"))
async def cmd_toggle_task(message: Message):
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("Использование: /toggle_task <id>")
        return
    try:
        task_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    with db_conn() as conn:
        task = get_task(conn, task_id)
        if not task:
            await message.answer(f"❌ Задача #{task_id} не найдена.")
            return
        new_active = not bool(task["is_active"])
        update_task_active(conn, task_id, new_active)
        updated_task = get_task(conn, task_id)

    if _pool_ref:
        from scheduler.task_runner import register_task, unregister_task
        from core.monitor import start_monitor, stop_monitor
        if new_active:
            if task["task_type"] == "post":
                register_task(_pool_ref, updated_task)
            else:
                start_monitor(_pool_ref, updated_task)
        else:
            if task["task_type"] == "post":
                unregister_task(task_id)
            else:
                stop_monitor(task_id)

    status = "▶️ активирована" if new_active else "⏸ приостановлена"
    await message.answer(f"Задача #{task_id} {status}.")

import os
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, PhotoSize
from db.database import get_conn
from db.models import create_post, list_posts, get_post, delete_post
from config import MEDIA_DIR

router = Router()


class AddPost(StatesGroup):
    waiting_title = State()
    waiting_content = State()


@router.message(Command("posts"))
async def cmd_posts(message: Message):
    conn = get_conn()
    posts = list_posts(conn)
    if not posts:
        await message.answer("Постов нет. /add_post — создать.")
        return
    lines = ["📝 <b>Посты:</b>\n"]
    for p in posts:
        img = " 🖼" if p.get("image_path") else ""
        lines.append(f"#{p['id']} {p['title']}{img}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("add_post"))
async def cmd_add_post(message: Message, state: FSMContext):
    await state.set_state(AddPost.waiting_title)
    await message.answer("Введи название поста (для поиска в меню):")


@router.message(AddPost.waiting_title)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AddPost.waiting_content)
    await message.answer(
        "Отправь текст поста (или фото с подписью).\n"
        "Или /skip чтобы оставить без текста."
    )


@router.message(AddPost.waiting_content, F.photo)
async def process_content_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    os.makedirs(MEDIA_DIR, exist_ok=True)
    photo: PhotoSize = message.photo[-1]
    file_path = os.path.join(MEDIA_DIR, f"{photo.file_id}.jpg")
    await message.bot.download(photo, destination=file_path)
    caption = message.caption or ""
    conn = get_conn()
    pid = create_post(conn, title=data["title"], text=caption, image_path=file_path)
    await message.answer(f"✅ Пост #{pid} «{data['title']}» сохранён с фото.")


@router.message(AddPost.waiting_content)
async def process_content_text(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    text = "" if message.text.strip() == "/skip" else message.text.strip()
    conn = get_conn()
    pid = create_post(conn, title=data["title"], text=text)
    await message.answer(f"✅ Пост #{pid} «{data['title']}» сохранён.")


@router.message(Command("del_post"))
async def cmd_del_post(message: Message):
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("Использование: /del_post <id>")
        return
    try:
        pid = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    conn = get_conn()
    if not get_post(conn, pid):
        await message.answer(f"❌ Пост #{pid} не найден.")
        return
    delete_post(conn, pid)
    await message.answer(f"✅ Пост #{pid} удалён.")

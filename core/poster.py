import logging
import os
from telethon import TelegramClient

logger = logging.getLogger(__name__)


async def send_post(client: TelegramClient, group_id: int, post: dict) -> int:
    """
    Send a post to a group. Returns message ID.
    Raises FloodWaitError if rate-limited — caller handles per-account sleep.
    Does NOT add random delay here; the caller (task_runner) handles jitter between groups.
    """
    text = post.get("text") or ""
    image_path = post.get("image_path")

    if image_path and os.path.exists(image_path):
        msg = await client.send_file(group_id, image_path, caption=text)
    else:
        msg = await client.send_message(group_id, text)
    return msg.id


async def send_comment(client: TelegramClient, message, post: dict) -> int:
    """
    Reply to a message with post content. Returns reply message ID.
    """
    text = post.get("text") or ""
    image_path = post.get("image_path")
    group_id = message.chat_id
    reply_to = message.id

    if image_path and os.path.exists(image_path):
        msg = await client.send_file(group_id, image_path,
                                     caption=text, reply_to=reply_to)
    else:
        msg = await client.send_message(group_id, text, reply_to=reply_to)
    return msg.id

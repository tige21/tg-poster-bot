import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.poster import send_post, send_comment


@pytest.mark.asyncio
async def test_send_post_text_only():
    client = MagicMock()
    client.send_message = AsyncMock(return_value=MagicMock(id=101))
    post = {"text": "hello"}
    msg_id = await send_post(client, group_id=1, post=post)
    assert msg_id == 101
    client.send_message.assert_called_once_with(1, "hello")


@pytest.mark.asyncio
async def test_send_post_with_image(tmp_path):
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"fake")
    client = MagicMock()
    client.send_file = AsyncMock(return_value=MagicMock(id=202))
    post = {"text": "caption", "image_path": str(img)}
    msg_id = await send_post(client, group_id=2, post=post)
    assert msg_id == 202
    client.send_file.assert_called_once_with(2, str(img), caption="caption")


@pytest.mark.asyncio
async def test_send_post_missing_image_falls_back_to_text(tmp_path):
    client = MagicMock()
    client.send_message = AsyncMock(return_value=MagicMock(id=303))
    post = {"text": "fallback", "image_path": "/nonexistent/path.jpg"}
    msg_id = await send_post(client, group_id=3, post=post)
    assert msg_id == 303
    client.send_message.assert_called_once_with(3, "fallback")


@pytest.mark.asyncio
async def test_send_comment_text_only():
    client = MagicMock()
    client.send_message = AsyncMock(return_value=MagicMock(id=404))
    message = MagicMock()
    message.chat_id = 10
    message.id = 50
    post = {"text": "reply text"}
    msg_id = await send_comment(client, message, post)
    assert msg_id == 404
    client.send_message.assert_called_once_with(10, "reply text", reply_to=50)


@pytest.mark.asyncio
async def test_send_comment_with_image(tmp_path):
    img = tmp_path / "img.jpg"
    img.write_bytes(b"data")
    client = MagicMock()
    client.send_file = AsyncMock(return_value=MagicMock(id=505))
    message = MagicMock()
    message.chat_id = 20
    message.id = 99
    post = {"text": "cap", "image_path": str(img)}
    msg_id = await send_comment(client, message, post)
    assert msg_id == 505
    client.send_file.assert_called_once_with(20, str(img), caption="cap", reply_to=99)

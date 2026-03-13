import pytest
from unittest.mock import AsyncMock, MagicMock
from core.account_pool import AccountPool


@pytest.mark.asyncio
async def test_pool_starts_empty():
    pool = AccountPool()
    assert pool.get_client(1) is None
    assert pool.list_ids() == []


@pytest.mark.asyncio
async def test_pool_add_and_get():
    pool = AccountPool()
    mock_client = MagicMock()
    mock_client.is_connected.return_value = True
    pool._clients[42] = mock_client
    assert pool.get_client(42) is mock_client


@pytest.mark.asyncio
async def test_pool_remove():
    pool = AccountPool()
    mock_client = AsyncMock()
    mock_client.is_connected.return_value = True
    pool._clients[1] = mock_client
    await pool.remove(1)
    assert pool.get_client(1) is None
    mock_client.disconnect.assert_called_once()

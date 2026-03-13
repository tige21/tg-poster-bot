import pytest
from unittest.mock import AsyncMock, patch
from core.proxy_checker import check_proxy


@pytest.mark.asyncio
async def test_check_proxy_ok():
    with patch("core.proxy_checker._tcp_connect", new=AsyncMock(return_value=150)):
        result = await check_proxy(type="socks5", host="1.2.3.4",
                                   port=1080, username=None, password=None)
    assert result["status"] == "ok"
    assert result["ping_ms"] == 150


@pytest.mark.asyncio
async def test_check_proxy_slow():
    with patch("core.proxy_checker._tcp_connect", new=AsyncMock(return_value=2500)):
        result = await check_proxy(type="socks5", host="1.2.3.4",
                                   port=1080, username=None, password=None)
    assert result["status"] == "slow"


@pytest.mark.asyncio
async def test_check_proxy_fail():
    with patch("core.proxy_checker._tcp_connect",
               new=AsyncMock(side_effect=OSError("refused"))):
        result = await check_proxy(type="socks5", host="1.2.3.4",
                                   port=1080, username=None, password=None)
    assert result["status"] == "fail"
    assert result["ping_ms"] is None

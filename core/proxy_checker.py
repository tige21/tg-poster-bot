import asyncio
import time


async def _tcp_connect(host: str, port: int) -> int:
    """
    Open TCP connection to host:port.
    Returns round-trip time in ms. Raises OSError on failure.
    Note: this verifies TCP reachability only, not SOCKS5 authentication.
    """
    start = time.monotonic()
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout=5
    )
    ms = int((time.monotonic() - start) * 1000)
    writer.close()
    await writer.wait_closed()
    return ms


async def check_proxy(*, type: str, host: str, port: int,
                      username: str | None, password: str | None) -> dict:
    """
    Check proxy reachability via TCP ping.
    Returns {'status': 'ok'|'slow'|'fail', 'ping_ms': int|None}
    Status thresholds: ok < 2000ms, slow >= 2000ms, fail = any exception.
    """
    try:
        ping_ms = await _tcp_connect(host, port)
        status = "slow" if ping_ms > 2000 else "ok"
        return {"status": status, "ping_ms": ping_ms}
    except Exception:
        return {"status": "fail", "ping_ms": None}

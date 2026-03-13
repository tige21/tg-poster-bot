import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)


def _make_proxy_tuple(proxy: dict | None) -> tuple | None:
    """
    Convert DB proxy dict to Telethon socks proxy tuple.
    Telethon accepts: (socks.SOCKS5, host, port, rdns, username, password)
    python-socks is NOT needed — Telethon bundles its own SOCKS support.
    """
    if not proxy or proxy.get("status") == "fail":
        return None
    import socks
    type_map = {
        "socks5": socks.SOCKS5,
        "socks4": socks.SOCKS4,
        "http":   socks.HTTP,
        "https":  socks.HTTP,
    }
    proxy_type = type_map.get(proxy["type"].lower(), socks.SOCKS5)
    return (
        proxy_type,
        proxy["host"],
        proxy["port"],
        True,  # rdns — resolve hostnames through proxy
        proxy.get("username"),
        proxy.get("password"),
    )


class AccountPool:
    """Manages a dict of account_id → TelegramClient in the shared event loop."""

    def __init__(self):
        self._clients: dict[int, TelegramClient] = {}

    def get_client(self, account_id: int) -> TelegramClient | None:
        return self._clients.get(account_id)

    def list_ids(self) -> list[int]:
        return list(self._clients.keys())

    async def add(self, account_id: int, session_string: str,
                  api_id: int, api_hash: str,
                  proxy: dict | None = None) -> TelegramClient:
        """Create and connect a Telethon client. Uses connect() only — no interactive auth."""
        proxy_tuple = _make_proxy_tuple(proxy)
        client = TelegramClient(
            StringSession(session_string or ""),
            api_id,
            api_hash,
            proxy=proxy_tuple,
        )
        await client.connect()
        self._clients[account_id] = client
        logger.info(f"Account {account_id} connected.")
        return client

    async def remove(self, account_id: int) -> None:
        client = self._clients.pop(account_id, None)
        if client and client.is_connected():
            await client.disconnect()

    async def start_all(self, conn) -> None:
        """Load all non-banned accounts from DB and connect them individually."""
        from db.models import list_accounts, get_proxy
        for acc in list_accounts(conn):
            if acc["status"] == "banned":
                continue
            if not acc.get("session_string"):
                continue
            proxy = get_proxy(conn, acc["proxy_id"]) if acc.get("proxy_id") else None
            try:
                await self.add(
                    acc["id"],
                    acc["session_string"],
                    acc["api_id"],
                    acc["api_hash"],
                    proxy,
                )
            except Exception as e:
                # One account failing must not block others
                logger.warning(f"Failed to connect account {acc['id']}: {e}")

    async def stop_all(self) -> None:
        for account_id in list(self._clients.keys()):
            await self.remove(account_id)

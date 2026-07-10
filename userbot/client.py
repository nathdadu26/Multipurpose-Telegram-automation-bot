import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import AuthKeyUnregisteredError, SessionRevokedError
from config.settings import settings

logger = logging.getLogger("userbot")


class UserbotClient:
    def __init__(self):
        self.client = TelegramClient(
            StringSession(settings.string_session),
            settings.api_id,
            settings.api_hash,
        )
        self._watch_task = None

    async def start(self):
        try:
            await self.client.start()
        except (AuthKeyUnregisteredError, SessionRevokedError):
            logger.error(
                "Userbot session expired/revoked. Generate a new STRING_SESSION "
                "using scripts/generate_session.py and update your .env."
            )
            raise
        me = await self.client.get_me()
        logger.info("Userbot connected as %s", getattr(me, "username", me.id))
        self._watch_task = asyncio.create_task(self._watch_connection())

    async def _watch_connection(self):
        while True:
            await asyncio.sleep(30)
            try:
                if not self.client.is_connected():
                    logger.warning("Userbot disconnected. Reconnecting...")
                    await self.client.connect()
                    if not await self.client.is_user_authorized():
                        logger.error("Userbot session no longer authorized.")
            except Exception as e:
                logger.error("Reconnect attempt failed: %s", e)

    async def stop(self):
        if self._watch_task:
            self._watch_task.cancel()
        await self.client.disconnect()


userbot = UserbotClient()

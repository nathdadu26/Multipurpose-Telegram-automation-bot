import asyncio
import logging

logger = logging.getLogger("auto_delete")


async def auto_delete(message, delay: int = 10):
    """Delete a Telegram message after `delay` seconds. Never raises."""
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except Exception as e:
        logger.debug("Auto-delete skipped: %s", e)

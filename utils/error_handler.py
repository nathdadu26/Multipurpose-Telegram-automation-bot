import logging
from functools import wraps

from telethon.errors import (
    FloodWaitError,
    RPCError,
    ChannelPrivateError,
    ChatWriteForbiddenError,
    ChannelInvalidError,
)
from telegram.error import TelegramError, NetworkError, TimedOut, RetryAfter

logger = logging.getLogger("errors")


def safe_handler(func):
    """Wrap a python-telegram-bot handler so it never crashes the bot and
    always reports a friendly error back to the admin in DM."""

    @wraps(func)
    async def wrapper(update, context, *a, **kw):
        try:
            return await func(update, context, *a, **kw)
        except RetryAfter as e:
            logger.warning("RetryAfter: %s", e.retry_after)
            if update.effective_message:
                await update.effective_message.reply_text(f"⚠ Rate limited, retry after {e.retry_after}s")
        except FloodWaitError as e:
            logger.warning("FloodWait: %s", e.seconds)
            if update.effective_message:
                await update.effective_message.reply_text(f"⚠ Flood wait: {e.seconds}s")
        except (ChannelPrivateError, ChatWriteForbiddenError, ChannelInvalidError) as e:
            logger.error("Channel access error: %s", e)
            if update.effective_message:
                await update.effective_message.reply_text(f"❌ Channel access error: {e}")
        except (NetworkError, TimedOut) as e:
            logger.error("Network error: %s", e)
            if update.effective_message:
                await update.effective_message.reply_text("❌ Network error, please try again.")
        except TelegramError as e:
            logger.error("Telegram error: %s", e)
            if update.effective_message:
                await update.effective_message.reply_text(f"❌ Error: {e}")
        except RPCError as e:
            logger.error("Telethon RPC error: %s", e)
            if update.effective_message:
                await update.effective_message.reply_text(f"❌ Telegram RPC error: {e}")
        except Exception as e:
            logger.exception("Unhandled error in handler")
            if update.effective_message:
                await update.effective_message.reply_text(f"❌ Unexpected error: {e}")

    return wrapper

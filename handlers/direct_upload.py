import io
import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from handlers.admin_filter import admin_only
from utils.error_handler import safe_handler
from database.repositories.channel_repo import channel_repo
from database.repositories.media_repo import media_repo
from config.settings import settings
from userbot.client import userbot

logger = logging.getLogger("direct_upload")


@admin_only
@safe_handler
async def handle_direct_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Any video sent directly to the bot's DM (no command) gets copied,
    without caption, into the current available target channel, then the
    original DM message is deleted."""
    msg = update.message
    if not msg.video:
        return

    # Bot API gives us file_unique_id for free — a ready-made dedup key,
    # no download needed to check it.
    dup_key = f"botapi:{msg.video.file_unique_id}"
    if await media_repo.exists(dup_key):
        await msg.reply_text("⏭ This video was already uploaded before — skipped as a duplicate.")
        try:
            await msg.delete()
        except Exception:
            pass
        return

    target = await channel_repo.get_available_channel(settings.channel_limit)
    if not target:
        await msg.reply_text("❌ No available target channel. All channels are full.")
        return

    tg_file = await msg.video.get_file()
    file_bytes = await tg_file.download_as_bytearray()
    buffer = io.BytesIO(bytes(file_bytes))
    buffer.name = (msg.video.file_name or "video") + ".mp4"

    await userbot.client.send_file(target["_id"], buffer, caption="")
    await channel_repo.increment_upload(target["_id"])
    await media_repo.record(dup_key, size=msg.video.file_size)

    try:
        await msg.delete()
    except Exception as e:
        logger.debug("Couldn't delete original DM media: %s", e)


direct_video_handler = MessageHandler(filters.VIDEO & filters.ChatType.PRIVATE, handle_direct_video)

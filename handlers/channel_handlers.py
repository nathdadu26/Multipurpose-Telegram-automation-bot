import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, filters

from handlers.admin_filter import admin_only
from utils.error_handler import safe_handler
from utils.auto_delete import auto_delete
from database.repositories.channel_repo import channel_repo
from userbot.folder_manager import add_to_target_channels_folder

logger = logging.getLogger("channels")

WAITING_FORWARD = 1


@admin_only
@safe_handler
async def add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📁 Forward any message from the target channel.")
    return WAITING_FORWARD


@admin_only
@safe_handler
async def add_channel_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    origin = msg.forward_origin

    if origin is None or not hasattr(origin, "chat"):
        await msg.reply_text("❌ That wasn't a forwarded channel message. Forward again, or /cancel.")
        return WAITING_FORWARD

    chat = origin.chat
    channel_id = chat.id
    title = chat.title or "Unknown"
    username = chat.username

    await channel_repo.add(channel_id, title, username)

    try:
        await add_to_target_channels_folder(channel_id)
    except Exception as e:
        logger.error("Couldn't add %s to 'Target Channels' folder: %s", title, e)

    success = await msg.reply_text(
        f"✅ <b>Channel Added</b>\n\n📁 {title}\n🆔 <code>{channel_id}</code>",
        parse_mode="HTML",
    )
    context.application.create_task(auto_delete(success, 10))
    return ConversationHandler.END


@admin_only
@safe_handler
async def cancel_conv(update, context):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


add_channel_conv = ConversationHandler(
    entry_points=[CommandHandler("add_channel", add_channel_start)],
    states={WAITING_FORWARD: [MessageHandler(filters.FORWARDED, add_channel_receive)]},
    fallbacks=[CommandHandler("cancel", cancel_conv)],
)


@admin_only
@safe_handler
async def list_channels(update, context):
    channels = await channel_repo.list_all()
    if not channels:
        await update.message.reply_text("📁 No target channels added yet. Use /add_channel.")
        return
    lines = ["📁 <b>Target Channels</b>\n"]
    for c in channels:
        status = "🟢" if c.get("active", True) else "🔴"
        lines.append(
            f"{status} {c['title']} — {c.get('total_uploaded', 0)}/2000 — <code>{c['_id']}</code>"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@admin_only
@safe_handler
async def remove_channel(update, context):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /remove_channel <channel_id>")
        return
    try:
        channel_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid channel ID.")
        return
    await channel_repo.remove(channel_id)
    success = await update.message.reply_text("✅ Channel removed.")
    context.application.create_task(auto_delete(success, 10))

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, filters

from handlers.admin_filter import admin_only
from utils.error_handler import safe_handler
from utils.auto_delete import auto_delete
from utils.parsers import parse_message_ref
from database.repositories.promotion_repo import promotion_repo
from database.repositories.group_repo import group_repo
from config.settings import settings
from userbot.client import userbot

logger = logging.getLogger("promotion")

WAITING_AD = 1
WAITING_GROUP = 2


@admin_only
@safe_handler
async def ad_promotion_start(update, context):
    await update.message.reply_text("📢 Send the promotional message (text / photo / video / animation).")
    return WAITING_AD


@admin_only
@safe_handler
async def ad_promotion_receive(update, context):
    msg = update.message

    sent = await context.bot.copy_message(
        chat_id=settings.ad_channel_id, from_chat_id=msg.chat_id, message_id=msg.message_id,
    )

    media_type = "text"
    if msg.photo:
        media_type = "photo"
    elif msg.video:
        media_type = "video"
    elif msg.animation:
        media_type = "animation"

    await promotion_repo.set_current(sent.message_id, media_type)

    try:
        await msg.delete()
    except Exception:
        pass

    groups = await group_repo.list_all()
    if groups:
        names = "\n".join(f"• {g['title']}" for g in groups)
        text = f"✅ <b>Promotion Set</b>\n\nWill be reposted hourly to:\n{names}"
    else:
        text = "✅ <b>Promotion Set</b>\n\n⚠ No groups added yet. Use /set_target to add groups."

    success = await context.bot.send_message(msg.chat_id, text, parse_mode="HTML")
    context.application.create_task(auto_delete(success, 10))
    return ConversationHandler.END


ad_promotion_conv = ConversationHandler(
    entry_points=[CommandHandler("ad_promotion", ad_promotion_start)],
    states={WAITING_AD: [MessageHandler(filters.ALL & ~filters.COMMAND, ad_promotion_receive)]},
    fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
)


@admin_only
@safe_handler
async def set_target_start(update, context):
    await update.message.reply_text("👥 Forward a message from the target group, or send its message link.")
    return WAITING_GROUP


@admin_only
@safe_handler
async def set_target_receive(update, context):
    msg = update.message
    origin = msg.forward_origin

    if origin is not None and hasattr(origin, "chat"):
        chat = origin.chat
        group_id, title, username = chat.id, chat.title, chat.username
    elif msg.text and "t.me/" in msg.text:
        ref, _ = parse_message_ref(msg.text)
        try:
            entity = await userbot.client.get_entity(ref)
        except Exception as e:
            await msg.reply_text(f"❌ Couldn't resolve that group: {e}")
            return WAITING_GROUP
        group_id = entity.id
        title = getattr(entity, "title", "Unknown")
        username = getattr(entity, "username", None)
    else:
        await msg.reply_text("❌ Please forward a group message or send a valid group link.")
        return WAITING_GROUP

    await group_repo.add(group_id, title, username)
    success = await msg.reply_text(f"✅ <b>Target Added</b>\n\n👥 {title}", parse_mode="HTML")
    context.application.create_task(auto_delete(success, 10))
    return ConversationHandler.END


set_target_conv = ConversationHandler(
    entry_points=[CommandHandler("set_target", set_target_start)],
    states={
        WAITING_GROUP: [MessageHandler((filters.FORWARDED | filters.TEXT) & ~filters.COMMAND, set_target_receive)]
    },
    fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
)


@admin_only
@safe_handler
async def list_groups(update, context):
    groups = await group_repo.list_all()
    if not groups:
        await update.message.reply_text("👥 No promotion groups added. Use /set_target.")
        return
    lines = ["👥 <b>Promotion Groups</b>\n"] + [f"• {g['title']}" for g in groups]
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler, filters

from handlers.admin_filter import admin_only
from utils.error_handler import safe_handler
from utils.auto_delete import auto_delete
from utils.parsers import parse_message_ref, build_message_link
from database.repositories.promotion_repo import promotion_repo
from database.repositories.group_repo import group_repo
from config.settings import settings
from userbot.client import userbot
from userbot.promo_poster import repost_via_userbot
from userbot.folder_manager import add_to_posted_groups_folder
from scheduler.promotion_scheduler import notify_group_failure

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
    resolution_warning = None
    group_link = None

    if origin is not None and hasattr(origin, "chat"):
        chat = origin.chat
        group_id, title, username = chat.id, chat.title, chat.username

        # Try to confirm the *userbot* can resolve this chat, but don't
        # block saving the group if it can't — just warn. The scheduled
        # promotion job (and its own dialog-refresh retry) will keep
        # retrying it automatically rather than requiring it to work
        # perfectly right at add-time.
        try:
            await userbot.client.get_entity(group_id)
        except Exception:
            try:
                await userbot.refresh_dialogs()
                await userbot.client.get_entity(group_id)
            except Exception as e:
                resolution_warning = str(e)

    elif msg.text and "t.me/" in msg.text:
        group_link = msg.text.strip()
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

    await group_repo.add(group_id, title, username, link=group_link)
    success = await msg.reply_text(f"✅ <b>Target Added</b>\n\n👥 {title}", parse_mode="HTML")
    context.application.create_task(auto_delete(success, 10))

    try:
        await add_to_posted_groups_folder(group_id)
    except Exception as e:
        logger.error("Couldn't add %s to 'Posted Groups' folder: %s", title, e)

    if resolution_warning:
        await msg.reply_text(
            f"⚠ <b>Saved, but userbot can't reach this group yet.</b>\n\n"
            f"👥 {title}\n"
            f"Make sure the userbot account is a member of this group — it will "
            f"be retried automatically on the next promotion cycle.\n\n"
            f"<i>Details: {resolution_warning}</i>",
            parse_mode="HTML",
        )

    # Post the current promotion to this group right away instead of making
    # it wait for the next hourly cycle. If this fails, the group is
    # deactivated immediately (no retries) and the admin is notified with
    # a button to the group, same as a failure during the hourly cycle.
    promo = await promotion_repo.get_current()
    if promo and promo.get("enabled"):
        try:
            sent = await repost_via_userbot(group_id, settings.ad_channel_id, promo["message_id"], username=username)
            await group_repo.increment_post_count(group_id)

            link = build_message_link(group_id, sent.id, username=username) if sent else None
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 View Post", url=link)]]) if link else None

            note = await msg.reply_text(
                f"📢 Posted the current promotion to <b>{title}</b> immediately.",
                parse_mode="HTML", reply_markup=keyboard,
            )
            if not keyboard:
                context.application.create_task(auto_delete(note, 10))
        except Exception as e:
            group_doc = await group_repo.get(group_id)
            await notify_group_failure(
                context.bot,
                group_doc or {"_id": group_id, "title": title, "username": username, "link": group_link},
                e,
            )
            await msg.reply_text(
                f"⚠ Group saved, but the immediate promotion post failed — this group has been "
                f"deactivated and will not be retried automatically.\nReason: {e}\n"
                f"Fix the issue, then use /set_target again."
            )

    return ConversationHandler.END


set_target_conv = ConversationHandler(
    entry_points=[CommandHandler("set_target", set_target_start)],
    states={
        WAITING_GROUP: [MessageHandler((filters.FORWARDED | filters.TEXT) & ~filters.COMMAND, set_target_receive)]
    },
    fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
)


GROUPS_PAGE_SIZE = 10


async def _build_groups_page(page: int):
    groups = await group_repo.list_all()
    total = len(groups)
    total_pages = max(1, (total + GROUPS_PAGE_SIZE - 1) // GROUPS_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * GROUPS_PAGE_SIZE
    chunk = groups[start:start + GROUPS_PAGE_SIZE]

    lines = ["👥 <b>Promoting in Groups</b>\n"]
    if not chunk:
        lines.append("No groups added yet. Use /set_target.")
    else:
        for g in chunk:
            lines.append(f"• {g['title']} - {g.get('total_posted', 0)} — <code>{g['_id']}</code>")
    text = "\n".join(lines)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("<<", callback_data=f"groups_page_{page - 1}" if page > 1 else "groups_noop"),
        InlineKeyboardButton(f"{page}", callback_data="groups_noop"),
        InlineKeyboardButton(">>", callback_data=f"groups_page_{page + 1}" if page < total_pages else "groups_noop"),
    ]])
    return text, keyboard


@admin_only
@safe_handler
async def list_groups(update, context):
    text, keyboard = await _build_groups_page(1)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


@admin_only
@safe_handler
async def groups_page_callback(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "groups_noop":
        return
    page = int(query.data.rsplit("_", 1)[-1])
    text, keyboard = await _build_groups_page(page)
    try:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        pass


@admin_only
@safe_handler
async def remove_group(update, context):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /remove_group <group_id>\n(Get the ID from /groups)")
        return
    try:
        group_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid group ID.")
        return
    await group_repo.remove(group_id)
    success = await update.message.reply_text("✅ Group removed.")
    context.application.create_task(auto_delete(success, 10))

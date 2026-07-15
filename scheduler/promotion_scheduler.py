import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from database.repositories.promotion_repo import promotion_repo
from database.repositories.group_repo import group_repo
from userbot.promo_poster import repost_via_userbot
from userbot.client import userbot
from config.settings import settings

logger = logging.getLogger("scheduler")

# Live state so /status can show "ad posting in progress" alongside a copy job.
_promo_state = {"running": False, "index": 0, "total": 0, "current_group": None}


def get_promotion_status():
    return dict(_promo_state)


def _group_link(group: dict):
    """The same link the group was registered with in /set_target, if one
    was given; otherwise fall back to a username-based link."""
    if group.get("link"):
        return group["link"]
    if group.get("username"):
        return f"https://t.me/{group['username']}"
    return None


async def notify_group_failure(bot, group: dict, error):
    """A group's post failed — it will NOT be retried automatically (no
    multi-strike grace period). Deactivate it immediately and tell the
    admin(s), with a button linking to the same group link used when it
    was added via /set_target."""
    await group_repo.set_active(group["_id"], False)

    link = _group_link(group)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Open Group", url=link)]]) if link else None

    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"⚠ <b>Group Deactivated</b>\n\n👥 {group['title']}\n\n"
                f"Posting failed, so this group will not be retried automatically.\n"
                f"Reason: {error}\n\n"
                f"Fix the issue (e.g. userbot needs to be a member), then use /set_target again.",
                parse_mode="HTML", reply_markup=keyboard,
            )
        except Exception:
            pass


async def repost_job(bot):
    """Runs every PROMOTION_INTERVAL seconds. Reposts the stored ad message
    (never the original) to each group sequentially, GROUP_POST_DELAY apart.

    Posting uses the Telethon userbot account rather than the Bot API, so
    this works even in groups where only the userbot (not the bot account)
    is a member/admin."""
    promo = await promotion_repo.get_current()
    if not promo or not promo.get("enabled"):
        logger.info("No active promotion to repost.")
        return

    # Verify the *source* ad message in AD_CHANNEL_ID still exists before
    # touching any group. Without this check, a deleted/expired source ad
    # (self-destruct timer, auto-delete chat setting, manual deletion, etc.)
    # would make every single group's post attempt fail — wrongly getting
    # every group deactivated for a problem that has nothing to do with the
    # groups themselves.
    try:
        source_msg = await userbot.client.get_messages(settings.ad_channel_id, ids=promo["message_id"])
    except Exception as e:
        logger.error("Couldn't check source ad message: %s", e)
        source_msg = None

    if source_msg is None:
        await promotion_repo.disable()
        logger.error("Source ad message (id=%s) is gone — promotion disabled, groups untouched.",
                     promo["message_id"])
        for admin_id in settings.admin_ids:
            try:
                await bot.send_message(
                    admin_id,
                    "⚠ <b>Promotion Ad Missing</b>\n\n"
                    "The staged ad message in your ad channel no longer exists — it may have "
                    "been deleted, had a self-destruct/auto-delete timer, or was removed manually. "
                    "This is unrelated to any group; none of your groups were penalized for it.\n\n"
                    "Promotion has been paused. Use /ad_promotion to stage a new one.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        return

    groups = await group_repo.list_all()
    if not groups:
        logger.info("No promotion groups configured.")
        return

    _promo_state.update(running=True, total=len(groups), index=0, current_group=None)
    try:
        for i, group in enumerate(groups, start=1):
            _promo_state.update(index=i, current_group=group["title"])
            try:
                await repost_via_userbot(
                    group["_id"], settings.ad_channel_id, promo["message_id"],
                    username=group.get("username"),
                )
                logger.info("Posted promotion to %s", group["title"])
                await group_repo.increment_post_count(group["_id"])
            except Exception as e:
                logger.error("Failed to post promotion to %s: %s — deactivating, no retry.", group["title"], e)
                await notify_group_failure(bot, group, e)
            await asyncio.sleep(settings.group_post_delay)
    finally:
        _promo_state.update(running=False, current_group=None)


def start_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        repost_job, "interval", seconds=settings.promotion_interval,
        args=[bot], id="promotion_repost", replace_existing=True,
    )
    scheduler.start()
    logger.info("Promotion scheduler started (every %ss)", settings.promotion_interval)
    return scheduler

import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.repositories.promotion_repo import promotion_repo
from database.repositories.group_repo import group_repo
from userbot.promo_poster import repost_via_userbot
from config.settings import settings

logger = logging.getLogger("scheduler")

# Live state so /status can show "ad posting in progress" alongside a copy job.
_promo_state = {"running": False, "index": 0, "total": 0, "current_group": None}


def get_promotion_status():
    return dict(_promo_state)


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
                await group_repo.record_success(group["_id"])
                await group_repo.increment_post_count(group["_id"])
            except Exception as e:
                logger.error("Failed to post promotion to %s: %s", group["title"], e)
                fail_count, deactivated = await group_repo.record_failure(group["_id"])
                for admin_id in settings.admin_ids:
                    try:
                        if deactivated:
                            await bot.send_message(
                                admin_id,
                                f"⚠ <b>Group Deactivated</b>\n\n👥 {group['title']}\n"
                                f"Failed {fail_count} times in a row ({e}).\n"
                                f"Removed from promotion rotation — re-add with /set_target once fixed.",
                                parse_mode="HTML",
                            )
                        else:
                            await bot.send_message(
                                admin_id,
                                f"⚠ <b>Promotion Failed</b>\n\n👥 {group['title']}\n"
                                f"Attempt {fail_count}/3\nReason: {e}",
                                parse_mode="HTML",
                            )
                    except Exception:
                        pass
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

import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.repositories.promotion_repo import promotion_repo
from database.repositories.group_repo import group_repo
from config.settings import settings

logger = logging.getLogger("scheduler")


async def repost_job(bot):
    """Runs every PROMOTION_INTERVAL seconds. Reposts the stored ad message
    (never the original) to each group sequentially, GROUP_POST_DELAY apart."""
    promo = await promotion_repo.get_current()
    if not promo or not promo.get("enabled"):
        logger.info("No active promotion to repost.")
        return

    groups = await group_repo.list_all()
    if not groups:
        logger.info("No promotion groups configured.")
        return

    for group in groups:
        try:
            await bot.copy_message(
                chat_id=group["_id"],
                from_chat_id=settings.ad_channel_id,
                message_id=promo["message_id"],
            )
            logger.info("Posted promotion to %s", group["title"])
            await group_repo.record_success(group["_id"])
        except Exception as e:
            logger.error("Failed to post promotion to %s: %s", group["title"], e)
            fail_count, deactivated = await group_repo.record_failure(group["_id"])
            try:
                if deactivated:
                    await bot.send_message(
                        settings.admin_id,
                        f"⚠ <b>Group Deactivated</b>\n\n👥 {group['title']}\n"
                        f"Failed {fail_count} times in a row ({e}).\n"
                        f"Removed from promotion rotation — re-add with /set_target once fixed.",
                        parse_mode="HTML",
                    )
                else:
                    await bot.send_message(
                        settings.admin_id,
                        f"⚠ <b>Promotion Failed</b>\n\n👥 {group['title']}\n"
                        f"Attempt {fail_count}/3\nReason: {e}",
                        parse_mode="HTML",
                    )
            except Exception:
                pass
        await asyncio.sleep(settings.group_post_delay)


def start_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        repost_job, "interval", seconds=settings.promotion_interval,
        args=[bot], id="promotion_repost", replace_existing=True,
    )
    scheduler.start()
    logger.info("Promotion scheduler started (every %ss)", settings.promotion_interval)
    return scheduler

import logging

from telegram import BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from config.settings import settings, validate
from utils.logger import setup_logging
from database.mongo import mongo
from userbot.client import userbot
from scheduler.promotion_scheduler import start_scheduler

from database.repositories.job_repo import job_repo
from handlers.status_handlers import start_cmd, help_cmd, status_cmd, stats_cmd, logs_cmd
from handlers.channel_handlers import add_channel_conv, list_channels, remove_channel
from handlers.copy_handlers import copy_all_conv, copy_button_handler, resume_cmd, cancel_cmd
from handlers.direct_upload import direct_video_handler
from handlers.promotion_handlers import ad_promotion_conv, set_target_conv, list_groups, groups_page_callback, remove_group

setup_logging()
logger = logging.getLogger("main")

COMMANDS = [
    BotCommand("start", "Start the bot"),
    BotCommand("help", "Show help"),
    BotCommand("copy_all", "Copy videos in a message range"),
    BotCommand("add_channel", "Add a target channel"),
    BotCommand("remove_channel", "Remove a target channel"),
    BotCommand("channels", "List target channels"),
    BotCommand("ad_promotion", "Set promotional message"),
    BotCommand("set_target", "Add promotion group"),
    BotCommand("groups", "List promotion groups"),
    BotCommand("remove_group", "Remove a promotion group"),
    BotCommand("cancel", "Cancel current job"),
    BotCommand("resume", "Resume paused job"),
    BotCommand("status", "Show job status"),
    BotCommand("logs", "Show recent logs"),
    BotCommand("stats", "Show stats"),
]


async def post_init(application):
    # register commands only if they differ from what's already set
    existing = await application.bot.get_my_commands()
    existing_names = {c.command for c in existing}
    wanted_names = {c.command for c in COMMANDS}
    if existing_names != wanted_names:
        await application.bot.set_my_commands(COMMANDS)
        logger.info("Bot commands registered")
    else:
        logger.info("Bot commands already up to date, skipping")

    mongo.connect()
    logger.info("Database connected")

    # A job left as "running" in the DB with no live in-process runner means
    # the bot restarted mid-job (redeploy, crash, etc). Demote it to
    # "paused" so it doesn't permanently block new /copy_all jobs and so
    # /resume can properly pick it back up.
    stale_jobs = await job_repo.get_all_running()
    for job in stale_jobs:
        await job_repo.update(job["_id"], status="paused")
        logger.warning("Job %s was left 'running' from a previous run — marked as 'paused'. Use /resume to continue it.", job["_id"])

    await userbot.start()

    application.bot_data["scheduler"] = start_scheduler(application.bot)

    logger.info("Startup complete — bot is online")


async def post_shutdown(application):
    logger.info("Shutting down...")
    await userbot.stop()
    mongo.close()


def main():
    validate()

    application = (
        Application.builder()
        .token(settings.bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("status", status_cmd))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("logs", logs_cmd))
    application.add_handler(CommandHandler("channels", list_channels))
    application.add_handler(CommandHandler("remove_channel", remove_channel))
    application.add_handler(CommandHandler("groups", list_groups))
    application.add_handler(CommandHandler("remove_group", remove_group))
    application.add_handler(CommandHandler("resume", resume_cmd))
    application.add_handler(CommandHandler("cancel", cancel_cmd))

    application.add_handler(add_channel_conv)
    application.add_handler(copy_all_conv)
    application.add_handler(ad_promotion_conv)
    application.add_handler(set_target_conv)

    application.add_handler(CallbackQueryHandler(copy_button_handler, pattern="^copy_"))
    application.add_handler(CallbackQueryHandler(groups_page_callback, pattern="^groups_"))
    application.add_handler(direct_video_handler)

    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()

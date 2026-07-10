import logging
from rich.logging import RichHandler
from config.settings import settings


def setup_logging():
    logging.basicConfig(
        level=settings.log_level,
        format="%(name)s: %(message)s",
        handlers=[
            RichHandler(rich_tracebacks=True, show_path=False),
            logging.FileHandler("bot.log", encoding="utf-8"),
        ],
    )
    # quiet down noisy libraries — we only want our own app-level logs
    # (channels/groups/copy/scheduler/errors) at INFO, not library internals
    # like Telethon's "Got difference for channel ..." update-sync chatter.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("telethon.client.updates").setLevel(logging.WARNING)
    logging.getLogger("telethon.network").setLevel(logging.WARNING)
    logging.getLogger("telethon.extensions.messagepacker").setLevel(logging.WARNING)

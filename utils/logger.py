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
    # quiet down noisy libraries
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _int(name, default=None):
    v = os.getenv(name, default)
    return int(v) if v is not None and v != "" else None


@dataclass
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    api_id: int = _int("API_ID")
    api_hash: str = os.getenv("API_HASH", "")
    string_session: str = os.getenv("STRING_SESSION", "")
    admin_id: int = _int("ADMIN_ID")
    ad_channel_id: int = _int("AD_CHANNEL_ID")

    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db_name: str = os.getenv("MONGO_DB_NAME", "telegram_bot")

    upload_delay: int = _int("UPLOAD_DELAY", "10")
    group_post_delay: int = _int("GROUP_POST_DELAY", "60")
    promotion_interval: int = _int("PROMOTION_INTERVAL", "3600")
    channel_limit: int = _int("CHANNEL_LIMIT", "2000")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()

REQUIRED = ["bot_token", "api_id", "api_hash", "string_session", "admin_id"]


def validate():
    missing = [f for f in REQUIRED if not getattr(settings, f)]
    if missing:
        raise RuntimeError(f"Missing required .env values: {', '.join(missing)}")

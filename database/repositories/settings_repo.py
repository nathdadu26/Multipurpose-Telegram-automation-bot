from database.mongo import mongo
from config.settings import settings as env_settings


class SettingsRepo:
    """Runtime-overridable settings, falling back to .env defaults."""

    @property
    def col(self):
        return mongo.db["settings"]

    async def get(self, key, default=None):
        doc = await self.col.find_one({"_id": key})
        return doc["value"] if doc else default

    async def set(self, key, value):
        await self.col.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)

    async def upload_delay(self):
        return await self.get("upload_delay", env_settings.upload_delay)

    async def group_post_delay(self):
        return await self.get("group_post_delay", env_settings.group_post_delay)

    async def promotion_interval(self):
        return await self.get("promotion_interval", env_settings.promotion_interval)


settings_repo = SettingsRepo()

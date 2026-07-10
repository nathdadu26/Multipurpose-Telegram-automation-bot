from database.mongo import mongo


class MediaRepo:
    """Duplicate detection without downloading anything.

    Telegram assigns each uploaded file a `document.id` on its own servers.
    Re-uploads/forwards of the exact same original file share that same ID
    (it's effectively Telegram's own content fingerprint) — so comparing
    `document.id` values lets us detect duplicates purely from message
    metadata, with zero bytes downloaded.
    """

    @property
    def col(self):
        return mongo.db["copied_media"]

    async def exists(self, doc_id: int) -> bool:
        return await self.col.find_one({"_id": doc_id}) is not None

    async def record(self, doc_id: int, size: int = None, source_message_id: int = None):
        await self.col.update_one(
            {"_id": doc_id},
            {"$setOnInsert": {"size": size, "source_message_id": source_message_id}},
            upsert=True,
        )


media_repo = MediaRepo()

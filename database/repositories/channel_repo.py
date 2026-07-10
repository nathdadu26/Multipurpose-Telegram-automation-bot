from database.mongo import mongo


class ChannelRepo:
    @property
    def col(self):
        return mongo.db["channels"]

    async def add(self, channel_id, title, username=None):
        doc = {
            "_id": channel_id,
            "title": title,
            "username": username,
            "total_uploaded": 0,
            "active": True,
        }
        await self.col.update_one({"_id": channel_id}, {"$setOnInsert": doc}, upsert=True)
        return await self.col.find_one({"_id": channel_id})

    async def get(self, channel_id):
        return await self.col.find_one({"_id": channel_id})

    async def list_all(self):
        return [d async for d in self.col.find({})]

    async def remove(self, channel_id):
        await self.col.delete_one({"_id": channel_id})

    async def increment_upload(self, channel_id, amount=1):
        await self.col.update_one({"_id": channel_id}, {"$inc": {"total_uploaded": amount}})

    async def get_available_channel(self, limit):
        """Return first active channel under capacity, ordered by insertion (acts as queue)."""
        channel = await self.col.find_one({"active": True, "total_uploaded": {"$lt": limit}})
        return channel

    async def set_active(self, channel_id, active):
        await self.col.update_one({"_id": channel_id}, {"$set": {"active": active}})


channel_repo = ChannelRepo()

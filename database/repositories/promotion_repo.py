from database.mongo import mongo


class PromotionRepo:
    @property
    def col(self):
        return mongo.db["promotion"]

    async def set_current(self, message_id, media_type):
        await self.col.update_one(
            {"_id": "current"},
            {"$set": {"message_id": message_id, "media_type": media_type, "enabled": True}},
            upsert=True,
        )

    async def get_current(self):
        return await self.col.find_one({"_id": "current"})

    async def disable(self):
        await self.col.update_one({"_id": "current"}, {"$set": {"enabled": False}}, upsert=True)


promotion_repo = PromotionRepo()

from database.mongo import mongo


class GroupRepo:
    @property
    def col(self):
        return mongo.db["groups"]

    async def add(self, group_id, title, username=None):
        doc = {
            "_id": group_id, "title": title, "username": username,
            "active": True, "fail_count": 0, "total_posted": 0,
        }
        await self.col.update_one({"_id": group_id}, {"$setOnInsert": doc}, upsert=True)
        return await self.col.find_one({"_id": group_id})

    async def list_all(self):
        return [d async for d in self.col.find({"active": True})]

    async def remove(self, group_id):
        await self.col.delete_one({"_id": group_id})

    async def record_failure(self, group_id, max_failures=3):
        """Increment consecutive-failure count; deactivate after max_failures.
        Returns (new_fail_count, deactivated: bool)."""
        doc = await self.col.find_one_and_update(
            {"_id": group_id}, {"$inc": {"fail_count": 1}}, return_document=True
        )
        fail_count = doc.get("fail_count", 1) if doc else 1
        deactivated = False
        if fail_count >= max_failures:
            await self.col.update_one({"_id": group_id}, {"$set": {"active": False}})
            deactivated = True
        return fail_count, deactivated

    async def record_success(self, group_id):
        await self.col.update_one({"_id": group_id}, {"$set": {"fail_count": 0}})

    async def increment_post_count(self, group_id, amount=1):
        await self.col.update_one({"_id": group_id}, {"$inc": {"total_posted": amount}})


group_repo = GroupRepo()

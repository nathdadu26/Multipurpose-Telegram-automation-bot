from database.mongo import mongo


class JobRepo:
    @property
    def col(self):
        return mongo.db["copy_jobs"]

    async def create_job(self, job_id, source_channel_id, start_message, end_message):
        doc = {
            "_id": job_id,
            "source_channel_id": source_channel_id,
            "start_message": start_message,
            "end_message": end_message,
            "current_message": start_message,
            "copied": 0,
            "skipped": 0,
            "status": "running",  # running | paused | cancelled | completed | stopped_no_channel
            "current_target_channel": None,
        }
        await self.col.insert_one(doc)
        return doc

    async def get(self, job_id):
        return await self.col.find_one({"_id": job_id})

    async def update(self, job_id, **fields):
        await self.col.update_one({"_id": job_id}, {"$set": fields})

    async def get_active_job(self):
        """Most recent job that is running or paused (for restart-resume)."""
        return await self.col.find_one(
            {"status": {"$in": ["running", "paused"]}}, sort=[("_id", -1)]
        )


job_repo = JobRepo()

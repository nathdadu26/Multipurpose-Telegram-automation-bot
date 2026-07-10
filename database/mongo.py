from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import settings


class Mongo:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    def connect(cls):
        cls.client = AsyncIOMotorClient(settings.mongo_uri)
        cls.db = cls.client[settings.mongo_db_name]
        return cls.db

    @classmethod
    def close(cls):
        if cls.client:
            cls.client.close()


mongo = Mongo()

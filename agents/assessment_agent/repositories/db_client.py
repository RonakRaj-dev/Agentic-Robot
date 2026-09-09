import os

from motor.motor_asyncio import AsyncIOMotorClient


class DatabaseManager:

    def __init__(self):
        self.uri = os.getenv(
            "MONGO_URI",
            "mongodb://localhost:27017",
        )

        self.db_name = os.getenv(
            "MONGO_DB_NAME",
            "SiliconRag",
        )

        self.client = None
        self.db = None

    async def get_db(self):

        if self.db is None:

            self.client = AsyncIOMotorClient(
                self.uri
            )

            self.db = self.client[
                self.db_name
            ]

        return self.db

    def close(self):

        if self.client:
            self.client.close()


db_manager = DatabaseManager()
import os

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "hotel")


class StorageUnavailable(Exception):
    pass


def connect_mongo(url: str = MONGO_URL, db_name: str = DB_NAME) -> Database:
    try:
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
    except PyMongoError as error:
        raise StorageUnavailable(f"MongoDB недоступна ({url}): {error}") from None
    return client[db_name]

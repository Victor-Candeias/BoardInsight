from datetime import UTC, datetime

from pymongo.database import Database


def utcnow() -> datetime:
    return datetime.now(UTC)


class Repository:
    collection_name: str

    def __init__(self, db: Database):
        self.db = db
        self.collection = db[self.collection_name]

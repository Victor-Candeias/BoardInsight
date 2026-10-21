from datetime import timedelta

from pymongo.errors import DuplicateKeyError

from app.repositories.base import Repository, utcnow


class LockRepository(Repository):
    """Lock exclusivo por nome (ex.: `sync:96`) com expiração (TTL) para locks órfãos."""

    collection_name = "locks"

    def acquire(self, name: str, owner: str, ttl: timedelta) -> bool:
        now = utcnow()
        try:
            self.collection.insert_one({"_id": name, "owner": owner, "acquiredAt": now, "expiresAt": now + ttl})
            return True
        except DuplicateKeyError:
            taken = self.collection.find_one_and_update(
                {"_id": name, "expiresAt": {"$lt": now}},
                {"$set": {"owner": owner, "acquiredAt": now, "expiresAt": now + ttl}},
            )
            return taken is not None

    def release(self, name: str, owner: str) -> None:
        self.collection.delete_one({"_id": name, "owner": owner})

    def is_locked(self, name: str) -> bool:
        return self.collection.count_documents({"_id": name, "expiresAt": {"$gte": utcnow()}}) > 0

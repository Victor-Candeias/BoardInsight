from typing import Any

from pymongo import ReturnDocument

from app.repositories.base import Repository, utcnow


class BoardRepository(Repository):
    collection_name = "boards"

    def find_all(self, search: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if search:
            import re

            pattern = re.escape(search)
            query = {"$or": [{"name": {"$regex": pattern, "$options": "i"}}, {"boardIdText": search}]}
        return list(self.collection.find(query, {"_id": 0}).sort("boardId", 1))

    def get(self, board_id: int) -> dict[str, Any] | None:
        return self.collection.find_one({"boardId": board_id}, {"_id": 0})

    def upsert_metadata(self, board_id: int, metadata: dict[str, Any]) -> dict[str, Any]:
        now = utcnow()
        return self.collection.find_one_and_update(
            {"boardId": board_id},
            {
                "$set": {**metadata, "boardIdText": str(board_id), "updatedAt": now},
                "$setOnInsert": {
                    "boardId": board_id,
                    "enabled": True,
                    "createdAt": now,
                    "lastSuccessfulSyncAt": None,
                    "sprints": {"cadence": None, "explicit": []},
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )

    def update(self, board_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        return self.collection.find_one_and_update(
            {"boardId": board_id},
            {"$set": {**fields, "updatedAt": utcnow()}},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )

    def delete(self, board_id: int) -> bool:
        return self.collection.delete_one({"boardId": board_id}).deleted_count == 1

    def enabled_ids(self) -> list[int]:
        return [b["boardId"] for b in self.collection.find({"enabled": True}, {"boardId": 1}).sort("boardId", 1)]

from datetime import datetime
from typing import Any

from app.repositories.base import Repository


class CardRepository(Repository):
    collection_name = "cards"

    def by_ids(self, board_id: int, card_ids: list[int] | None = None, projection: dict | None = None) -> dict[int, dict[str, Any]]:
        query: dict[str, Any] = {"boardId": board_id}
        if card_ids is not None:
            query["cardId"] = {"$in": card_ids}
        return {d["cardId"]: d for d in self.collection.find(query, projection or {"_id": 0, "raw": 0})}

    def upsert_many(self, docs: list[dict[str, Any]], seen_at: datetime) -> dict[str, int]:
        if not docs:
            return {"upserted": 0, "modified": 0, "matched": 0}
        upserted = modified = matched = 0
        for d in docs:
            result = self.collection.update_one(
                {"boardId": d["boardId"], "cardId": d["cardId"]},
                {
                    "$set": {**d, "lastSeenAt": seen_at, "rawUpdatedAt": seen_at, "missingSince": None},
                    "$setOnInsert": {"firstSeenAt": seen_at},
                },
                upsert=True,
            )
            upserted += result.upserted_id is not None
            modified += result.modified_count
            matched += result.matched_count
        return {"upserted": upserted, "modified": modified, "matched": matched}

    def active_ids(self, board_id: int) -> set[int]:
        return {d["cardId"] for d in self.collection.find({"boardId": board_id, "state": "active"}, {"cardId": 1})}

    def mark_missing(self, board_id: int, card_ids: list[int], now: datetime) -> int:
        if not card_ids:
            return 0
        result = self.collection.update_many(
            {"boardId": board_id, "cardId": {"$in": card_ids}, "missingSince": None},
            {"$set": {"missingSince": now}},
        )
        return result.modified_count

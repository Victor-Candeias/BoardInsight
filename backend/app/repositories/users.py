from typing import Any

from app.repositories.base import Repository, utcnow


class UserCacheRepository(Repository):
    """Nomes dos utilizadores Businessmap (para apresentação), por board."""

    collection_name = "users_cache"

    def replace_for_board(self, board_id: int, users: list[dict[str, Any]]) -> None:
        now = utcnow()
        for u in users:
            self.collection.update_one(
                {"boardId": board_id, "userId": u["userId"]},
                {"$set": {"name": u["name"], "username": u.get("username"), "updatedAt": now}},
                upsert=True,
            )

    def names(self, board_id: int) -> dict[int, str]:
        return {d["userId"]: d["name"] for d in self.collection.find({"boardId": board_id}, {"userId": 1, "name": 1})}

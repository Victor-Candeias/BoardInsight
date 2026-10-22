from datetime import timedelta
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.repositories.base import Repository, utcnow


def public_export(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


class ReportExportRepository(Repository):
    """Metadados dos ficheiros gerados (`report_exports`): pending → running → done | error.

    O índice TTL em `expiresAt` remove os documentos; os ficheiros são limpos pela retenção.
    """

    collection_name = "report_exports"

    def create(self, data: dict[str, Any], retention: timedelta) -> dict[str, Any]:
        now = utcnow()
        doc = {
            **data,
            "status": "pending",
            "createdAt": now,
            "startedAt": None,
            "finishedAt": None,
            "expiresAt": now + retention,
            "jobId": None,
            "fileName": None,
            "size": None,
            "rows": None,
            "error": None,
        }
        doc["_id"] = self.collection.insert_one(doc).inserted_id
        return public_export(doc)

    def get(self, export_id: str) -> dict[str, Any] | None:
        try:
            oid = ObjectId(export_id)
        except (InvalidId, TypeError):
            return None
        return public_export(self.collection.find_one({"_id": oid}))

    def update(self, export_id: str, fields: dict[str, Any]) -> None:
        self.collection.update_one({"_id": ObjectId(export_id)}, {"$set": fields})

    def recent(self, board_id: int | None, limit: int) -> list[dict[str, Any]]:
        query = {} if board_id is None else {"boardId": board_id}
        return [public_export(d) for d in self.collection.find(query).sort("createdAt", -1).limit(limit)]

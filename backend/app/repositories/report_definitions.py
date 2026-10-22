from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.repositories.base import Repository, utcnow


class DuplicateName(Exception):
    pass


def _public(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def _oid(definition_id: str) -> ObjectId | None:
    try:
        return ObjectId(definition_id)
    except (InvalidId, TypeError):
        return None


class ReportDefinitionRepository(Repository):
    """Definições de relatórios guardadas (`report_definitions`): nome único por board."""

    collection_name = "report_definitions"

    def for_board(self, board_id: int) -> list[dict[str, Any]]:
        return [_public(d) for d in self.collection.find({"boardId": board_id}).sort("name", 1)]

    def get(self, definition_id: str) -> dict[str, Any] | None:
        oid = _oid(definition_id)
        return _public(self.collection.find_one({"_id": oid})) if oid else None

    def create(self, board_id: int, name: str, params: dict[str, Any], schedule: dict[str, Any] | None = None) -> dict[str, Any]:
        now = utcnow()
        doc = {"boardId": board_id, "name": name, "params": params, "schedule": schedule, "createdAt": now, "updatedAt": now}
        try:
            doc["_id"] = self.collection.insert_one(doc).inserted_id
        except DuplicateKeyError:
            raise DuplicateName(name) from None
        return _public(doc)

    def update(
        self, definition_id: str, name: str, params: dict[str, Any], schedule: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        oid = _oid(definition_id)
        if oid is None:
            return None
        try:
            doc = self.collection.find_one_and_update(
                {"_id": oid},
                {"$set": {"name": name, "params": params, "schedule": schedule, "updatedAt": utcnow()}},
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            raise DuplicateName(name) from None
        return _public(doc)

    def scheduled(self) -> list[dict[str, Any]]:
        return [_public(d) for d in self.collection.find({"schedule.enabled": True})]

    def record_schedule_run(self, definition_id: str, fields: dict[str, Any]) -> None:
        self.collection.update_one({"_id": ObjectId(definition_id)}, {"$set": {f"schedule.{k}": v for k, v in fields.items()}})

    def delete(self, definition_id: str) -> bool:
        oid = _oid(definition_id)
        return bool(oid) and self.collection.delete_one({"_id": oid}).deleted_count == 1

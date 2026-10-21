from datetime import timedelta
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument

from app.repositories.base import Repository, utcnow

ACTIVE_STATUSES = ("pending", "running")


def public_job(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


class JobRepository(Repository):
    """Fila de jobs em MongoDB: pending → running → done | error."""

    collection_name = "jobs"

    def enqueue(self, job_type: str, payload: dict[str, Any], *, dedupe: bool = True) -> tuple[dict[str, Any], bool]:
        """Cria um job; com `dedupe`, devolve o job ativo equivalente se já existir. Devolve (job, criado)."""
        if dedupe:
            existing = self.collection.find_one(
                {"type": job_type, "payload": payload, "status": {"$in": list(ACTIVE_STATUSES)}}, sort=[("createdAt", 1)]
            )
            if existing:
                return public_job(existing), False
        doc = {
            "type": job_type,
            "payload": payload,
            "status": "pending",
            "attempts": 0,
            "createdAt": utcnow(),
            "startedAt": None,
            "finishedAt": None,
            "result": None,
            "error": None,
        }
        doc["_id"] = self.collection.insert_one(doc).inserted_id
        return public_job(doc), True

    def get(self, job_id: str) -> dict[str, Any] | None:
        try:
            oid = ObjectId(job_id)
        except (InvalidId, TypeError):
            return None
        return public_job(self.collection.find_one({"_id": oid}))

    def claim(self, worker: str) -> dict[str, Any] | None:
        now = utcnow()
        doc = self.collection.find_one_and_update(
            {"status": "pending"},
            {"$set": {"status": "running", "startedAt": now, "worker": worker}, "$inc": {"attempts": 1}},
            sort=[("createdAt", 1)],
            return_document=ReturnDocument.AFTER,
        )
        return public_job(doc)

    def finish(
        self,
        job_id: str,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        retention: timedelta = timedelta(days=7),
    ) -> None:
        now = utcnow()
        self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": status, "finishedAt": now, "result": result, "error": error, "expiresAt": now + retention}},
        )

    def fail_stale(self, older_than: timedelta, retention: timedelta = timedelta(days=7)) -> int:
        """Jobs `running` há demasiado tempo (worker morreu) passam a erro."""
        now = utcnow()
        result = self.collection.update_many(
            {"status": "running", "startedAt": {"$lt": now - older_than}},
            {
                "$set": {
                    "status": "error",
                    "finishedAt": now,
                    "error": {"code": "timeout", "message": "job interrompido ou sem resposta"},
                    "expiresAt": now + retention,
                }
            },
        )
        return result.modified_count

    def latest_for(self, job_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        return public_job(self.collection.find_one({"type": job_type, "payload": payload}, sort=[("createdAt", -1)]))

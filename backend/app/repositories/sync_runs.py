from typing import Any

from bson import ObjectId

from app.repositories.base import Repository, utcnow


def _public(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


class SyncRunRepository(Repository):
    collection_name = "sync_runs"

    def start(self, board_id: int, trigger: str, job_id: str | None = None) -> str:
        result = self.collection.insert_one(
            {"boardId": board_id, "trigger": trigger, "jobId": job_id, "status": "running", "startedAt": utcnow()}
        )
        return str(result.inserted_id)

    def finish(self, run_id: str, status: str, stats: dict[str, Any], error: dict[str, Any] | None = None) -> None:
        now = utcnow()
        run = self.collection.find_one({"_id": ObjectId(run_id)}, {"startedAt": 1})
        duration = (now - run["startedAt"]).total_seconds() * 1000 if run else None
        self.collection.update_one(
            {"_id": ObjectId(run_id)},
            {"$set": {"status": status, "finishedAt": now, "durationMs": round(duration or 0), "stats": stats, "error": error}},
        )

    def recent(self, board_id: int, limit: int = 20) -> list[dict[str, Any]]:
        cursor = self.collection.find({"boardId": board_id}).sort("startedAt", -1).limit(limit)
        return [_public(d) for d in cursor]

    def latest(self, board_id: int) -> dict[str, Any] | None:
        return _public(self.collection.find_one({"boardId": board_id}, sort=[("startedAt", -1)]))

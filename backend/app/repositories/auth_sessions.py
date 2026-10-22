import hashlib
import secrets
from datetime import datetime, timedelta

from app.repositories.base import Repository, utcnow
from app.services.auth import AuthUser

# A expiração por inatividade só é renovada se tiver passado este tempo (evita uma escrita por pedido).
TOUCH_INTERVAL = timedelta(seconds=60)


def token_id(token: str) -> str:
    """Só o hash do token fica na base de dados: uma cópia da BD não dá sessões válidas."""
    return hashlib.sha256(token.encode()).hexdigest()


class AuthSessionRepository(Repository):
    collection_name = "auth_sessions"

    def create(self, user: AuthUser, idle_ttl: timedelta, max_age: timedelta) -> str:
        token = secrets.token_urlsafe(32)
        now = utcnow()
        self.collection.insert_one(
            {
                "_id": token_id(token),
                "username": user.username,
                "name": user.name,
                "email": user.email,
                "createdAt": now,
                "lastSeenAt": now,
                "absoluteExpiresAt": now + max_age,
                "expiresAt": min(now + idle_ttl, now + max_age),
            }
        )
        return token

    def get(self, token: str, idle_ttl: timedelta) -> AuthUser | None:
        """Devolve o utilizador da sessão válida e prolonga a expiração por inatividade."""
        if not token:
            return None
        now = utcnow()
        doc = self.collection.find_one({"_id": token_id(token), "expiresAt": {"$gt": now}})
        if doc is None:
            return None
        if now - _aware(doc["lastSeenAt"]) >= TOUCH_INTERVAL:
            self.collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"lastSeenAt": now, "expiresAt": min(now + idle_ttl, _aware(doc["absoluteExpiresAt"]))}},
            )
        return AuthUser(username=doc["username"], name=doc["name"], email=doc["email"])

    def delete(self, token: str) -> None:
        if token:
            self.collection.delete_one({"_id": token_id(token)})


def _aware(value: datetime) -> datetime:
    # O MongoDB devolve datas naive (UTC) quando o cliente não usa tz_aware.
    return value if value.tzinfo else value.replace(tzinfo=utcnow().tzinfo)

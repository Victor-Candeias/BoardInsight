"""Ligação ao MongoDB 4.4 (PyMongo síncrono, datas sempre em UTC com timezone)."""

from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import Settings, get_settings


def create_client(settings: Settings) -> MongoClient:
    return MongoClient(
        settings.mongo_connection_uri(),
        tz_aware=True,
        serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
        connectTimeoutMS=settings.mongodb_timeout_ms,
        appname="BoardInsight",
        maxPoolSize=10,
    )


@lru_cache
def get_client() -> MongoClient:
    return create_client(get_settings())


def get_database() -> Database:
    """Dependência FastAPI; substituída nos testes por uma base mongomock."""
    return get_client()[get_settings().mongodb_database]

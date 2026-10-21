from typing import Annotated

from fastapi import Depends
from pymongo.database import Database

from app.core.config import Settings, get_settings
from app.core.database import get_database
from app.integrations.businessmap import BusinessmapClient
from app.services.sync import ClientFactory

DB = Annotated[Database, Depends(get_database)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_client_factory(settings: AppSettings) -> ClientFactory:
    return lambda: BusinessmapClient.from_settings(settings)


BmClientFactory = Annotated[ClientFactory, Depends(get_client_factory)]

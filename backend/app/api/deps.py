from typing import Annotated

from fastapi import Depends
from pymongo.database import Database

from app.core.config import Settings, get_settings
from app.core.database import get_database

DB = Annotated[Database, Depends(get_database)]
AppSettings = Annotated[Settings, Depends(get_settings)]

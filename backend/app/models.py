"""Model registry.

Importing this module registers every ORM model on `Base.metadata`. Alembic and the test suite
import it so that metadata is complete; application code imports models from their own modules.
"""

from app.db.base import Base
from app.modules.audit.models import AuditLog
from app.modules.auth.models import RefreshToken, User
from app.modules.catalog.models import Airport, City, Flight, Hotel, HotelAmenity, RoomType
from app.modules.ingestion.models import ImportReject, ImportRun

__all__ = [
    "Airport",
    "AuditLog",
    "Base",
    "City",
    "Flight",
    "Hotel",
    "HotelAmenity",
    "ImportReject",
    "ImportRun",
    "RefreshToken",
    "RoomType",
    "User",
]

"""Model registry.

Importing this module registers every ORM model on `Base.metadata`. Alembic and the test suite
import it so that metadata is complete; application code imports models from their own modules.
"""

from app.db.base import Base
from app.modules.audit.models import AuditLog
from app.modules.auth.models import RefreshToken, User
from app.modules.bookings.models import (
    Booking,
    BookingEvent,
    BookingItem,
    BookingTraveller,
    Payment,
    Refund,
    Trip,
)
from app.modules.catalog.models import Airport, City, Flight, Hotel, HotelAmenity, RoomType
from app.modules.ingestion.models import ImportReject, ImportRun
from app.modules.inventory.models import FlightInventory, InventoryClaim, RoomNightInventory
from app.modules.notifications.models import Notification
from app.modules.operations.models import Disruption
from app.modules.planner.models import TripPlan
from app.modules.recovery.models import RecoveryCase

__all__ = [
    "Airport",
    "AuditLog",
    "Base",
    "Booking",
    "BookingEvent",
    "BookingItem",
    "BookingTraveller",
    "City",
    "Disruption",
    "Flight",
    "FlightInventory",
    "Hotel",
    "HotelAmenity",
    "ImportReject",
    "ImportRun",
    "InventoryClaim",
    "Notification",
    "Payment",
    "RecoveryCase",
    "RefreshToken",
    "Refund",
    "RoomNightInventory",
    "RoomType",
    "Trip",
    "TripPlan",
    "User",
]

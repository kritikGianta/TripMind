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
    BookingExtra,
    BookingItem,
    BookingTraveller,
    Payment,
    Refund,
    Trip,
)
from app.modules.catalog.models import Airport, City, Flight, Hotel, HotelAmenity, RoomType
from app.modules.groups.models import GroupMember, GroupVote, TripGroup
from app.modules.ingestion.models import ImportReject, ImportRun
from app.modules.inventory.models import FlightInventory, InventoryClaim, RoomNightInventory
from app.modules.loyalty.module import LoyaltyEntry
from app.modules.ml.interactions import HotelInteraction
from app.modules.notifications.models import Notification
from app.modules.operations.models import Disruption
from app.modules.planner.models import TripPlan
from app.modules.profiles.module import TravellerProfile
from app.modules.recovery.models import RecoveryCase
from app.modules.search.history import SearchHistory
from app.modules.watchlist.models import PriceAlert, SavedHotel

__all__ = [
    "Airport",
    "AuditLog",
    "Base",
    "Booking",
    "BookingEvent",
    "BookingExtra",
    "BookingItem",
    "BookingTraveller",
    "City",
    "Disruption",
    "Flight",
    "FlightInventory",
    "GroupMember",
    "GroupVote",
    "Hotel",
    "HotelAmenity",
    "HotelInteraction",
    "ImportReject",
    "ImportRun",
    "InventoryClaim",
    "LoyaltyEntry",
    "Notification",
    "Payment",
    "PriceAlert",
    "RecoveryCase",
    "RefreshToken",
    "Refund",
    "RoomNightInventory",
    "RoomType",
    "SavedHotel",
    "SearchHistory",
    "TravellerProfile",
    "Trip",
    "TripGroup",
    "TripPlan",
    "User",
]

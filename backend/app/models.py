"""Model registry.

Importing this module registers every ORM model on `Base.metadata`. Alembic and the test suite
import it so that metadata is complete; application code imports models from their own modules.
"""

from app.db.base import Base
from app.modules.audit.models import AuditLog
from app.modules.auth.models import RefreshToken, User

__all__ = ["AuditLog", "Base", "RefreshToken", "User"]

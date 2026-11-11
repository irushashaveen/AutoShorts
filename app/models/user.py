import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum
from app.database import Base


class UserRole(str, enum.Enum):
    """Role-Based Access Control (RBAC) user permission tiers."""
    ADMIN = "admin"
    OPERATOR = "operator"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=True, index=True)
    hashed_password = Column(String(256), nullable=False)
    role = Column(
        Enum(UserRole, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.OPERATOR,
        nullable=False,
        index=True
    )
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    @property
    def is_operator(self) -> bool:
        """Helper to check if user possesses operator curation privileges."""
        return self.role in (UserRole.ADMIN, UserRole.OPERATOR) or str(self.role).lower() in ("admin", "operator")

    @property
    def is_operator(self) -> bool:
        """Helper to check if user possesses operator curation privileges."""
        return self.role in (UserRole.ADMIN, UserRole.OPERATOR) or str(self.role).lower() in ("admin", "operator")

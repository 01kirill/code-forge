import hashlib
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from codeforge.common.contracts import Document, Role, User


@dataclass(frozen=True)
class Account:
    id: UUID
    email: str
    name: str
    password_hash: str
    role: Role
    timezone: str
    active: bool
    version: int
    sessions_after: int

    def identity(self) -> Document:
        return {
            "id": str(self.id),
            "name": self.name,
            "role": self.role,
            "timezone": self.timezone,
            "active": self.active,
            "version": self.version,
            "sessions_after": self.sessions_after,
        }

    def principal(self, sid: UUID) -> User:
        return User(
            str(self.id), self.name, self.role, self.timezone, self.version, str(sid)
        )


@dataclass(frozen=True)
class RefreshSession:
    digest: str
    sid: UUID
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None = None


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

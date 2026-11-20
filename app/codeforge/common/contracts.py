from dataclasses import dataclass
from typing import Any, Literal, Protocol

type Document = dict[str, Any]
Role = Literal["student", "teacher", "admin"]


class Problem(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        detail: str,
        **context: str,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.context = context


@dataclass(frozen=True)
class User:
    id: str
    name: str
    role: Role
    timezone: str
    version: int
    sid: str
    exp: int = 0

    @property
    def teaches(self) -> bool:
        return self.role in ("teacher", "admin")


def check_owner(user: User, owner_id: str) -> None:
    if user.role != "admin" and (not user.teaches or user.id != owner_id):
        raise Problem(403, "forbidden", "Недостаточно прав")


class SubmissionLimiter(Protocol):
    async def check(self, user: User) -> None: ...


class LiveEvents(Protocol):
    async def send(self, channel: str, kind: str, **payload: Any) -> None: ...

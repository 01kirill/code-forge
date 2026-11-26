import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

type Document = dict[str, Any]
Role = Literal["student", "teacher", "admin"]


class JudgeLanguage(TypedDict):
    id: int
    name: str
    syntax: str


JUDGE_LANGUAGES: dict[str, JudgeLanguage] = json.loads(
    Path(__file__).with_name("judge_languages.json").read_text(encoding="utf-8")
)


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


QUEUE_LIMIT = 100


def check_queue(count: int) -> None:
    if count >= QUEUE_LIMIT:
        raise Problem(429, "judge_busy", "Очередь проверки заполнена. Повторите позже")


def queue_age(oldest: datetime | None, now: datetime) -> int:
    return max(0, int((now - oldest).total_seconds())) if oldest else 0


class LiveEvents(Protocol):
    async def send(self, channel: str, kind: str, **payload: Any) -> None: ...

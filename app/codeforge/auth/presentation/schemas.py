from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, EmailStr, Field, field_validator

Name = Annotated[str, Field(pattern=r"^[A-Za-z0-9_]{3,32}$")]
Password = Annotated[str, Field(min_length=8, max_length=72)]


class Login(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(max_length=72)]


class Registration(Login):
    name: Name
    password: Password


class ProfileEdit(BaseModel):
    name: Name
    timezone: Annotated[str, Field(max_length=64)]

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
        return value


class AccessEdit(BaseModel):
    role: Literal["student", "teacher"] | None = None
    active: bool | None = None


class AccessToken(BaseModel):
    access_token: str

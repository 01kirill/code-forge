import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
)
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis

from codeforge.common.contracts import Problem, User

ACCESS_SECONDS = 900
bearer = HTTPBearer(auto_error=False)


class Tokens:
    def __init__(
        self, public_key: Path, redis: Redis, private_key: Path | None = None
    ) -> None:
        verification_key = load_pem_public_key(public_key.read_bytes())
        signing_key = (
            load_pem_private_key(private_key.read_bytes(), None)
            if private_key
            else None
        )
        if not isinstance(verification_key, RSAPublicKey):
            raise ValueError("Expected an RSA public key")
        if signing_key is not None and not isinstance(signing_key, RSAPrivateKey):
            raise ValueError("Expected an RSA private key")
        self.public_key = verification_key
        self.private_key = signing_key
        self.redis = redis

    def issue(self, user: User) -> str:
        if self.private_key is None:
            raise RuntimeError("Signing key required")
        now = datetime.now(UTC)
        payload = asdict(user) | {
            "sub": user.id,
            "iss": "codeforge",
            "iat": now,
            "exp": now + timedelta(seconds=ACCESS_SECONDS),
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    async def verify(self, token: str) -> User:
        try:
            data = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                issuer="codeforge",
                options={"require": ["exp", "iat", "sub", "sid"]},
            )
            user = User(
                str(UUID(data["sub"])),
                data["name"],
                data["role"],
                data["timezone"],
                data["version"],
                str(UUID(data["sid"])),
                data["exp"],
            )
            if user.role not in ("student", "teacher", "admin"):
                raise ValueError
        except (jwt.InvalidTokenError, KeyError, ValueError, TypeError) as exc:
            raise Problem(401, "session", "Войдите в аккаунт") from exc
        return await self.current(user)

    async def current(self, user: User) -> User:
        values = await self.redis.mget(f"identity:{user.id}", f"revoked:{user.sid}")
        if user.exp <= datetime.now(UTC).timestamp() or values[1]:
            raise Problem(401, "session", "Войдите в аккаунт")
        if values[0]:
            state = json.loads(values[0])
            if not state["active"]:
                raise Problem(403, "blocked", "Аккаунт заблокирован")
            if state.get("sessions_after", 0) > user.version:
                raise Problem(401, "session", "Войдите в аккаунт")
            if state["version"] >= user.version:
                return replace(
                    user,
                    name=state["name"],
                    role=state["role"],
                    timezone=state["timezone"],
                )
        return user


async def optional_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User | None:
    if credentials is None:
        return None
    tokens: Tokens = request.app.state.tokens
    return await tokens.verify(credentials.credentials)


async def signed_in(user: Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise Problem(401, "session", "Войдите в аккаунт")
    return user


CurrentUser = Annotated[User, Depends(signed_in)]
OptionalUser = Annotated[User | None, Depends(optional_user)]

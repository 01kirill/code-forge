import base64
import hashlib

import bcrypt
from starlette.concurrency import run_in_threadpool

DUMMY_HASH = "sha256-v1:$2b$12$LQv3c1yqBWVHxkd0LHAkCOoTyEyn4b6i.T/Dchouj2WmiZbQmwZqG"


def password_bytes(password: str) -> bytes:
    return base64.b64encode(hashlib.sha256(password.encode()).digest())


def hash_password(password: str) -> str:
    digest = bcrypt.hashpw(password_bytes(password), bcrypt.gensalt(rounds=12))
    return "sha256-v1:" + digest.decode()


def check_password(password: str, stored: str) -> bool:
    version, digest = stored.split(":", maxsplit=1)
    return version == "sha256-v1" and bcrypt.checkpw(
        password_bytes(password), digest.encode()
    )


class BcryptPasswords:
    async def hash(self, password: str) -> str:
        return await run_in_threadpool(hash_password, password)

    async def matches(self, password: str, stored: str | None) -> bool:
        # The dummy hash keeps the same bcrypt cost when the account is absent.
        return await run_in_threadpool(check_password, password, stored or DUMMY_HASH)

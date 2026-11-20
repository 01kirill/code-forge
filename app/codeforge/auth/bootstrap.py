import argparse
import asyncio
import os
from getpass import getpass

from redis.asyncio import Redis

from codeforge.auth.application.accounts import Accounts
from codeforge.auth.infrastructure.passwords import BcryptPasswords
from codeforge.auth.infrastructure.postgres import PostgresAccounts
from codeforge.auth.infrastructure.redis import RedisSessions
from codeforge.auth.presentation.schemas import Registration
from codeforge.common.runtime import postgres, settings
from codeforge.common.security import Tokens


async def create(data: Registration) -> None:
    cfg = settings()
    async with (
        postgres(cfg.auth_db) as pool,
        Redis.from_url(cfg.redis_url, decode_responses=True) as redis,
    ):
        accounts = Accounts(
            PostgresAccounts(pool),
            BcryptPasswords(),
            RedisSessions(redis),
            Tokens(cfg.public_key, redis, cfg.private_key),
        )
        result = await accounts.first_administrator(
            data.email, data.name, data.password
        )
        if result is None:
            raise SystemExit("An administrator already exists.")
    print(f"Administrator created: {result['name']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    options = parser.parse_args()
    password = os.getenv("CODEFORGE_ADMIN_PASSWORD") or getpass(
        "Administrator password: "
    )
    asyncio.run(
        create(Registration(email=options.email, name=options.name, password=password))
    )


if __name__ == "__main__":
    main()

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from codeforge.auth.application.accounts import Accounts
from codeforge.auth.infrastructure.passwords import BcryptPasswords
from codeforge.auth.infrastructure.postgres import PostgresAccounts
from codeforge.auth.infrastructure.redis import RedisSessions
from codeforge.auth.presentation.http import router
from codeforge.common.broker import connect, publish_pending
from codeforge.common.http import application
from codeforge.common.runtime import postgres, recurring, resources, settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg = settings()
    app.state.secure_cookie = cfg.secure_cookie
    async with (
        resources(app, signing=True) as redis,
        postgres(cfg.auth_db) as pool,
        connect(cfg.rabbit_url) as broker,
    ):
        state = RedisSessions(redis)
        accounts = Accounts(
            PostgresAccounts(pool), BcryptPasswords(), state, app.state.tokens
        )
        app.state.accounts = accounts
        async with recurring(
            partial(publish_pending, pool, broker, state.publish_identity)
        ):
            yield


app = application("Auth", lifespan)
app.include_router(router)

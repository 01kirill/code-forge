from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

import httpx
from fastapi import FastAPI

from codeforge.common.broker import connect, publish_pending
from codeforge.common.http import application
from codeforge.common.redis_adapters import RedisLiveEvents, RedisSubmissionLimiter
from codeforge.common.runtime import postgres, recurring, resources, settings
from codeforge.contest.application.rooms import Contests
from codeforge.contest.infrastructure.postgres import PostgresContests
from codeforge.contest.infrastructure.services import (
    EducationTaskBank,
    RedisStandingsCache,
)
from codeforge.contest.presentation.http import router, sockets


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg = settings()
    async with (
        resources(app) as redis,
        postgres(cfg.contest_db) as pool,
        connect(cfg.rabbit_url) as broker,
        httpx.AsyncClient(
            base_url=cfg.education_url,
            headers={"X-Internal-Key": cfg.internal_key},
            timeout=3,
        ) as http,
    ):
        contests = Contests(
            PostgresContests(pool),
            EducationTaskBank(http),
            RedisStandingsCache(redis),
            RedisLiveEvents(redis),
            RedisSubmissionLimiter(redis),
        )
        app.state.contests = contests
        await broker.consume("contest.events", contests.sync_user)
        await broker.consume("judge.result.contest", contests.result)
        async with recurring(
            partial(publish_pending, pool, broker), contests.tick, contests.recover
        ):
            yield


app = application("Contest", lifespan)
app.include_router(sockets)
app.include_router(router)

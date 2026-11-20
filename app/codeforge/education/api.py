from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI
from pymongo import AsyncMongoClient

from codeforge.common.broker import connect
from codeforge.common.contracts import Document
from codeforge.common.http import application
from codeforge.common.redis_adapters import RedisLiveEvents, RedisSubmissionLimiter
from codeforge.common.runtime import recurring, resources, settings
from codeforge.education.application.content import Content
from codeforge.education.application.progress import Progress
from codeforge.education.application.submissions import Submissions
from codeforge.education.infrastructure.mongo import MongoEducation
from codeforge.education.infrastructure.services import (
    RabbitJudgements,
    RedisCourseCache,
    RedisPracticeLimiter,
)
from codeforge.education.presentation.http import internal, router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg = settings()
    app.state.internal_key = cfg.internal_key
    client: AsyncMongoClient[Document]
    async with (
        resources(app) as redis,
        AsyncMongoClient(cfg.mongo_url, tz_aware=True) as client,
        connect(cfg.rabbit_url) as broker,
    ):
        store = MongoEducation(client)
        await store.initialize()
        live = RedisLiveEvents(redis)
        content = Content(store, RedisCourseCache(redis))
        progress = Progress(store, content, live)
        submissions = Submissions(
            store,
            content,
            progress,
            live,
            RedisSubmissionLimiter(redis),
            RedisPracticeLimiter(redis),
        )
        app.state.content = content
        app.state.progress = progress
        app.state.submissions = submissions

        async def event(key: str, data: Document) -> None:
            if key == "contest.finished":
                await progress.prize(data)
            else:
                await store.sync_user(data)
                if key == "user.updated":
                    await live.send(f"edu:user:{data['id']}", "identity.updated")

        await broker.consume("education.events", event)
        await broker.consume("judge.result.education", submissions.apply_result)
        async with recurring(partial(submissions.dispatch, RabbitJudgements(broker))):
            yield


app = application("Education", lifespan)
app.include_router(internal)
app.include_router(router)

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from codeforge.common.contracts import Problem, User
from codeforge.common.http import BackgroundJob
from codeforge.common.security import Tokens

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    rabbit_url: str = os.getenv("RABBIT_URL", "amqp://guest:guest@localhost/")
    auth_db: str = os.getenv("AUTH_DB", "postgresql://auth:auth@localhost/auth")
    contest_db: str = os.getenv(
        "CONTEST_DB", "postgresql://contest:contest@localhost/contest"
    )
    mongo_url: str = os.getenv("MONGO_URL", "mongodb://localhost:27017/?replicaSet=rs0")
    education_url: str = os.getenv("EDUCATION_URL", "http://localhost:8002")
    judge_url: str = os.getenv("JUDGE_URL", "http://localhost:2358")
    public_key: Path = Path(os.getenv("JWT_PUBLIC_KEY", ".local/keys/public.pem"))
    private_key: Path = Path(os.getenv("JWT_PRIVATE_KEY", ".local/keys/private.pem"))
    internal_key: str = os.getenv("INTERNAL_KEY", "")
    secure_cookie: bool = os.getenv("SECURE_COOKIE", "true") == "true"


def settings() -> Settings:
    return Settings()


@asynccontextmanager
async def resources(app: FastAPI, *, signing: bool = False) -> AsyncIterator[Redis]:
    cfg = settings()
    async with Redis.from_url(cfg.redis_url, decode_responses=True) as redis:
        await redis.execute_command("PING")
        app.state.tokens = Tokens(
            cfg.public_key, redis, cfg.private_key if signing else None
        )
        app.state.redis = redis
        yield redis


@asynccontextmanager
async def postgres(url: str) -> AsyncIterator[asyncpg.Pool]:
    async def initialize(conn: asyncpg.Connection) -> None:
        await conn.set_type_codec(
            "jsonb",
            schema="pg_catalog",
            encoder=json.dumps,
            decoder=json.loads,
        )

    async with asyncpg.create_pool(
        url, min_size=1, max_size=12, init=initialize
    ) as pool:
        yield pool


@asynccontextmanager
async def recurring(*jobs: BackgroundJob) -> AsyncIterator[None]:
    async def repeat(job: BackgroundJob) -> None:
        operation = job.func if isinstance(job, partial) else job
        name = getattr(operation, "__qualname__", type(operation).__name__)
        while True:
            try:
                await job()
            except Exception as exc:
                logger.warning("%s failed: %s", name, type(exc).__name__)
            await asyncio.sleep(0.35)

    tasks = [asyncio.create_task(repeat(job)) for job in jobs]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def socket_user(ws: WebSocket) -> User:
    tokens: Tokens = ws.app.state.tokens
    return await tokens.verify(ws.query_params.get("token", ""))


async def stream(ws: WebSocket, user: User, *channels: str) -> None:
    redis: Redis = ws.app.state.redis
    tokens: Tokens = ws.app.state.tokens
    async with redis.pubsub() as sub:
        await sub.subscribe(*channels)
        await tokens.current(user)
        await ws.accept()

        async def forward() -> None:
            last_check = 0.0
            loop = asyncio.get_running_loop()
            while True:
                if loop.time() - last_check >= 2:
                    await tokens.current(user)
                    last_check = loop.time()
                message = await sub.get_message(
                    ignore_subscribe_messages=True, timeout=1
                )
                if message:
                    await ws.send_text(message["data"])

        async def receive() -> None:
            async for _ in ws.iter_text():
                pass

        jobs = [asyncio.create_task(forward()), asyncio.create_task(receive())]
        try:
            done, _ = await asyncio.wait(jobs, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except Problem:
            with suppress(RuntimeError):
                await ws.close(code=4401)
        except WebSocketDisconnect:
            pass
        finally:
            for task in jobs:
                task.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)

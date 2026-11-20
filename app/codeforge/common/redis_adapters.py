import json
from typing import Any

from redis.asyncio import Redis

from codeforge.common.contracts import Problem, User


class RedisLiveEvents:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def send(self, channel: str, kind: str, **payload: Any) -> None:
        await self.redis.publish(
            channel, json.dumps({"type": kind, **payload}, default=str)
        )


class RedisSubmissionLimiter:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def check(self, user: User) -> None:
        if not await self.redis.set(f"rl:submit:{user.id}", "1", ex=3, nx=True):
            raise Problem(429, "submit_limit", "Подождите три секунды перед отправкой")

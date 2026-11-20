import json

from redis.asyncio import Redis

from codeforge.common.broker import Broker
from codeforge.common.contracts import Document, Problem, User


class RedisCourseCache:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def key(slug: str, revision: str) -> str:
        return f"cache:course:{slug}:{revision}"

    async def get(self, slug: str, revision: str) -> Document | None:
        raw = await self.redis.get(self.key(slug, revision))
        value: Document | None = json.loads(raw) if raw else None
        return value

    async def save(self, slug: str, revision: str, course: Document) -> None:
        await self.redis.set(self.key(slug, revision), json.dumps(course), ex=300)

    async def drop(self, slug: str, revision: str) -> None:
        await self.redis.delete(self.key(slug, revision))


class RedisPracticeLimiter:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def check_practice(self, user: User) -> None:
        if not await self.redis.set(f"rl:run:{user.id}", "1", ex=3, nx=True):
            raise Problem(429, "submit_limit", "Подождите три секунды перед запуском")


class RabbitJudgements:
    def __init__(self, broker: Broker) -> None:
        self.broker = broker

    async def publish(self, key: str, event: Document) -> None:
        await self.broker.publish("judge", key, event)

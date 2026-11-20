import json

from redis.asyncio import Redis

from codeforge.common.contracts import Document
from codeforge.common.security import ACCESS_SECONDS

LOGIN_LIMIT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], 60) end
return count
"""
PUBLISH_IDENTITY = """
local old = redis.call('GET', KEYS[1])
if not old or cjson.decode(old).version < cjson.decode(ARGV[1]).version then
    redis.call('SET', KEYS[1], ARGV[1])
end
"""


class RedisSessions:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def log_login(self, ip: str, email: str) -> int:
        return int(
            await self.redis.execute_command(
                "EVAL", LOGIN_LIMIT, 1, f"rl:login:{ip}:{email}"
            )
        )

    async def publish_identity(self, key: str, event: Document) -> None:
        await self.redis.execute_command(
            "EVAL", PUBLISH_IDENTITY, 1, f"identity:{event['id']}", json.dumps(event)
        )

    async def revoke(self, sid: str) -> None:
        await self.redis.set(f"revoked:{sid}", "1", ex=ACCESS_SECONDS)

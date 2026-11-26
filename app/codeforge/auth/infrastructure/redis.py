import json

from redis.asyncio import Redis

from codeforge.common.contracts import Document
from codeforge.common.security import ACCESS_SECONDS

RATE_LIMIT = """
local allowed = 1
for i, key in ipairs(KEYS) do
    local count = redis.call('INCR', key)
    if count == 1 then redis.call('EXPIRE', key, 60) end
    if count > tonumber(ARGV[i]) then allowed = 0 end
end
return allowed
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

    async def allow_login(self, ip: str, email: str) -> bool:
        return bool(
            await self.redis.execute_command(
                "EVAL",
                RATE_LIMIT,
                3,
                f"rl:login:pair:{ip}:{email}",
                f"rl:login:ip:{ip}",
                f"rl:login:account:{email}",
                5,
                90,
                12,
            )
        )

    async def allow_registration(self, ip: str) -> bool:
        return bool(
            await self.redis.execute_command(
                "EVAL", RATE_LIMIT, 1, f"rl:register:{ip}", 90
            )
        )

    async def publish_identity(self, key: str, event: Document) -> None:
        await self.redis.execute_command(
            "EVAL", PUBLISH_IDENTITY, 1, f"identity:{event['id']}", json.dumps(event)
        )

    async def activate(self, sid: str) -> None:
        await self.redis.set(f"session:{sid}", "1", ex=ACCESS_SECONDS + 5)

    async def revoke(self, sid: str) -> None:
        await self.redis.delete(f"session:{sid}")

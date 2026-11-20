import json
from uuid import UUID

import httpx
from redis.asyncio import Redis

from codeforge.common.contracts import Document, Problem

CACHE_WRITE = """
local cached = redis.call('GET', KEYS[1])
if not cached or cjson.decode(cached).version <= tonumber(ARGV[1]) then
    redis.call('SET', KEYS[1], ARGV[2], 'EX', 36000)
end
"""


class EducationTaskBank:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def snapshot(self, task_id: str) -> Document:
        try:
            response = await self.http.get(f"/internal/tasks/{task_id}/public")
            if response.status_code == 404:
                raise Problem(
                    422, "task_unavailable", "Задача недоступна для соревнований"
                )
            response.raise_for_status()
            doc: Document = response.json()
            return doc
        except httpx.HTTPError as exc:
            raise Problem(503, "unavailable", "Банк задач временно недоступен") from exc


class RedisStandingsCache:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def get(self, contest: UUID) -> Document:
        cached = await self.redis.get(f"contest:{contest}:standings")
        data: Document = json.loads(cached) if cached else {}
        return data

    async def save(self, contest: UUID, revision: int, rows: list[Document]) -> None:
        await self.redis.execute_command(
            "EVAL",
            CACHE_WRITE,
            1,
            f"contest:{contest}:standings",
            revision,
            json.dumps({"version": revision, "rows": rows}),
        )

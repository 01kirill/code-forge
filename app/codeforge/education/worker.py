import asyncio
import os

import httpx
from pymongo import AsyncMongoClient

from codeforge.common.broker import connect
from codeforge.common.contracts import Document
from codeforge.common.runtime import settings
from codeforge.education.application.judging import JudgeSubmissions
from codeforge.education.infrastructure.judge0 import Judge
from codeforge.education.infrastructure.mongo import MongoEducation
from codeforge.education.infrastructure.services import RabbitJudgements


async def main() -> None:
    cfg = settings()
    client: AsyncMongoClient[Document]
    token = os.getenv("JUDGE_AUTH_TOKEN")
    headers = {"X-Auth-Token": token} if token else {}
    async with (
        AsyncMongoClient(cfg.mongo_url, tz_aware=True) as client,
        connect(cfg.rabbit_url, prefetch=4) as broker,
        httpx.AsyncClient(
            base_url=cfg.judge_url, headers=headers, timeout=httpx.Timeout(4, connect=2)
        ) as http,
    ):
        store = MongoEducation(client)
        judge = Judge(http, trusted_limits=os.getenv("JUDGE_TRUSTED_LIMITS") == "true")
        await broker.consume(
            "judge.request",
            JudgeSubmissions(store, RabbitJudgements(broker), judge).handle,
        )
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())

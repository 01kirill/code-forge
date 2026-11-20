import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from codeforge.common.contracts import Document
from codeforge.education.application.ports import (
    JudgementQueue,
    JudgementRepository,
    JudgeUnavailable,
    Runner,
)
from codeforge.education.application.views import now
from codeforge.education.domain.verdicts import Case, aggregate, technical

REPLIES = {"judge.result.education", "judge.result.contest"}


class JudgeSubmissions:
    def __init__(
        self, store: JudgementRepository, queue: JudgementQueue, runner: Runner
    ) -> None:
        self.store = store
        self.queue = queue
        self.runner = runner

    async def handle(self, key: str, job: Document) -> None:
        reply = job["reply"]
        if reply not in REPLIES:
            raise ValueError("Unknown result route")
        id_ = job["id"]
        saved = await self.store.judgement(id_)
        if saved and "result" in saved:
            await self.queue.publish(reply, {"id": id_, "result": saved["result"]})
            return

        at = now()
        lease = uuid4().hex
        claim = await self.store.claim(id_, lease, at, at + timedelta(seconds=32))
        if claim is None:
            return
        result = await self.evaluate(job, claim)
        if await self.store.finish_judgement(id_, lease, result):
            await self.queue.publish(reply, {"id": id_, "result": result})

    async def evaluate(self, job: Document, claim: Document) -> Document:
        remaining = 30 - (now() - claim["started_at"]).total_seconds()
        submitted = datetime.fromisoformat(job["submitted_at"])
        if remaining <= 0 or (now() - submitted).total_seconds() > 300:
            return technical()
        try:
            async with asyncio.timeout(remaining):
                task = await self.store.task_version(job["task_id"], job["version"])
                if not task or job["language"] not in task["templates"]:
                    return technical()
                cases = get_cases(task, job)
                if not cases:
                    return technical()
                tokens = claim.get("tokens")
                if not tokens:
                    tokens = await self.runner.start(
                        task,
                        job["language"],
                        job["code"],
                        cases,
                    )
                    await self.store.save_tokens(job["id"], claim["lease"], tokens)
                return aggregate(cases, await self.runner.collect(tokens))
        except (JudgeUnavailable, TimeoutError, ValueError, KeyError, TypeError):
            return technical()


def get_cases(task: Document, job: Document) -> list[Case]:
    if job["practice"] and job.get("stdin") is not None:
        return [Case(job["stdin"], None, True)]
    return [
        Case(test["stdin"], test["expected"], test["public"])
        for test in task["tests"]
        if not job["practice"] or test["public"]
    ]

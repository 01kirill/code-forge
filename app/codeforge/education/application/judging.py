import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from codeforge.common.contracts import Document
from codeforge.education.application.ports import (
    JudgeJob,
    JudgementQueue,
    JudgementRepository,
    JudgeUnavailable,
    Runner,
)
from codeforge.education.application.views import now
from codeforge.education.domain.verdicts import (
    Case,
    JudgementResult,
    aggregate,
    technical,
    wall_seconds,
)

COMPILE_WALL_SECONDS = 12  # Matches MAX_WALL_TIME_LIMIT in compose.judge.yml.

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

        request: JudgeJob = {
            "id": id_,
            "task_id": job["task_id"],
            "version": job["version"],
            "language": job["language"],
            "code": job["code"],
            "practice": job["practice"],
            "submitted_at": datetime.fromisoformat(job["submitted_at"]),
            "stdin": job.get("stdin"),
        }
        task = await self.store.task_version(request["task_id"], request["version"])
        if task is not None and request["language"] not in task["templates"]:
            task = None
        cases = get_cases(task, request) if task is not None else []
        budget = judging_budget(task["time_ms"] if task else 0, len(cases))
        at = now()
        lease = uuid4().hex
        claim = await self.store.claim(
            id_, lease, at, at + timedelta(seconds=budget + 2)
        )
        if claim is None:
            return
        result = await self.evaluate(request, task, cases, claim, budget)
        if await self.store.finish_judgement(id_, lease, result):
            await self.queue.publish(reply, {"id": id_, "result": result})

    async def evaluate(
        self,
        job: JudgeJob,
        task: Document | None,
        cases: list[Case],
        claim: Document,
        budget: float,
    ) -> JudgementResult:
        started: datetime = claim["started_at"]
        remaining = budget - (now() - started).total_seconds()
        if (
            not task
            or not cases
            or remaining <= 0
            or (started - job["submitted_at"]).total_seconds() > 300
        ):
            return technical()
        try:
            async with asyncio.timeout(remaining):
                tokens = claim.get("tokens")
                if not tokens:
                    tokens = await self.runner.start(
                        task, job["language"], job["code"], cases
                    )
                    await self.store.save_tokens(job["id"], claim["lease"], tokens)
                return aggregate(cases, await self.runner.collect(tokens))
        except (JudgeUnavailable, TimeoutError, ValueError, KeyError, TypeError):
            return technical()


def judging_budget(time_ms: int, case_count: int) -> float:
    # Budget for one worker, including compilation and a buffer for queue and API time.
    return 30 + case_count * (COMPILE_WALL_SECONDS + wall_seconds(time_ms))


def get_cases(task: Document, job: JudgeJob) -> list[Case]:
    stdin = job["stdin"]
    if job["practice"] and stdin is not None:
        return [Case(stdin, None, True)]
    return [
        Case(test["stdin"], test["expected"], test["public"])
        for test in task["tests"]
        if not job["practice"] or test["public"]
    ]

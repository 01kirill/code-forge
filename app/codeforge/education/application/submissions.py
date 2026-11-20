from datetime import timedelta
from uuid import uuid4

from codeforge.common.contracts import (
    Document,
    LiveEvents,
    Problem,
    SubmissionLimiter,
    User,
)
from codeforge.education.application.content import Content
from codeforge.education.application.ports import (
    EducationData,
    EducationRepository,
    JudgementQueue,
    PracticeLimiter,
    SubmissionDraft,
)
from codeforge.education.application.progress import Progress
from codeforge.education.application.views import now
from codeforge.education.domain import LESSON_XP, Verdict, changes, grant, task_xp


def public_submission(doc: Document) -> Document:
    fields = (
        "id",
        "user_id",
        "task_id",
        "lesson_id",
        "task_title",
        "course_slug",
        "language",
        "code",
        "submitted_at",
        "state",
        "result",
    )
    return {key: doc[key] for key in fields if key in doc}


class Submissions:
    def __init__(
        self,
        store: EducationRepository,
        content: Content,
        progress: Progress,
        events: LiveEvents,
        limiter: SubmissionLimiter,
        practice: PracticeLimiter,
    ) -> None:
        self.store = store
        self.content = content
        self.progress = progress
        self.events = events
        self.limiter = limiter
        self.practice = practice

    async def create(self, task_id: str, data: SubmissionDraft, user: User) -> Document:
        lesson, _ = await self.content.lesson(data.lesson_id, user)
        if lesson.get("task_id") != task_id:
            raise Problem(404, "task_missing", "Задача не найдена")
        task = await self.content.task(task_id)
        if data.language not in task["templates"]:
            raise Problem(422, "language", "Этот язык не поддерживается задачей")
        if data.practice:
            await self.practice.check_practice(user)
        else:
            await self.limiter.check(user)

        async def save(tx: EducationData) -> Document:
            sequence = await tx.next_sequence(user.id)
            at = now()
            doc = {
                "id": uuid4().hex,
                "task_id": task_id,
                "version": task["id"],
                "task_title": task["title"],
                "difficulty": task["difficulty"],
                "lesson_id": data.lesson_id,
                "course_slug": lesson["course_slug"],
                "user_id": user.id,
                "timezone": user.timezone,
                "language": data.language,
                "code": data.code,
                "practice": data.practice,
                "sequence": sequence,
                "state": "queued",
                "submitted_at": at,
                "dispatch_after": at,
            }
            if data.practice:
                doc.update(stdin=data.stdin, expires_at=at + timedelta(minutes=10))
            await tx.add_submission(doc)
            return public_submission(doc)

        return await self.store.transaction(save)

    async def get(self, id_: str, user: User) -> Document:
        doc = await self.store.submission(id_, user.id)
        if doc is None:
            raise Problem(404, "submission_missing", "Попытка не найдена")
        return public_submission(doc)

    async def list(
        self,
        user: User,
        task_id: str | None = None,
        offset: int = 0,
    ) -> list[Document]:
        return [
            {
                key: value
                for key, value in public_submission(doc).items()
                if key != "code"
            }
            for doc in await self.store.submissions(user.id, task_id, offset)
        ]

    async def dispatch(self, queue: JudgementQueue) -> None:
        at = now()
        async for doc in self.store.due_submissions(at):
            await queue.publish(
                "judge.request",
                {
                    "id": doc["id"],
                    "task_id": doc["task_id"],
                    "version": doc["version"],
                    "language": doc["language"],
                    "code": doc["code"],
                    "practice": doc["practice"],
                    "stdin": doc.get("stdin"),
                    "reply": "judge.result.education",
                    "submitted_at": doc["submitted_at"].isoformat(),
                },
            )
            await self.store.schedule_dispatch(
                doc["id"],
                doc["dispatch_after"],
                at + timedelta(seconds=45),
            )

    async def apply_result(self, key: str, event: Document) -> None:
        async def save(tx: EducationData) -> tuple[Document, Document | None] | None:
            attempt = await tx.finish_submission(event["id"], event["result"])
            if attempt is None:
                return None
            if attempt["practice"]:
                return attempt, None

            profile = await tx.profile_for_result(attempt["user_id"])
            assert profile is not None
            before = {
                "xp": profile["xp"],
                "achievements": profile.get("achievements", {}).copy(),
            }
            failures = 0
            async for item in tx.task_history(attempt["user_id"], attempt["task_id"]):
                if item["state"] == "queued":
                    break
                verdict = item["result"]["verdict"]
                if verdict == Verdict.TECHNICAL:
                    continue
                if verdict != Verdict.AC:
                    failures += 1
                    continue
                was_solved = item["task_id"] in profile.get("solved", {})
                at, zone = item["submitted_at"], item["timezone"]
                grant(
                    profile,
                    "task",
                    item["task_id"],
                    task_xp(item["difficulty"], failures),
                    at,
                    zone,
                    first_try=failures == 0,
                )
                if not was_solved:
                    profile["solved"][item["task_id"]]["lesson_id"] = item["lesson_id"]
                grant(profile, "lesson", item["lesson_id"], LESSON_XP, at, zone)
            await tx.save_profile(profile)
            return attempt, changes(before, profile)

        outcome = await self.store.transaction(save)
        if outcome:
            attempt, update = outcome
            await self.events.send(
                f"edu:user:{attempt['user_id']}",
                "submission.result",
                id=event["id"],
                result=event["result"],
                practice=attempt["practice"],
            )
            if update:
                await self.progress.notify(attempt["user_id"], update)

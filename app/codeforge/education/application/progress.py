from datetime import datetime

from codeforge.common.contracts import Document, LiveEvents, Problem, User
from codeforge.education.application.content import Content
from codeforge.education.application.ports import EducationData, EducationRepository
from codeforge.education.application.views import now
from codeforge.education.domain import (
    ACHIEVEMENTS,
    LESSON_XP,
    PLACE_XP,
    changes,
    grant,
    level,
    percent,
    streaks,
)


class Progress:
    def __init__(
        self, store: EducationRepository, content: Content, events: LiveEvents
    ) -> None:
        self.store = store
        self.content = content
        self.events = events

    async def notify(self, user_id: str, update: Document) -> None:
        channel = f"edu:user:{user_id}"
        if update["level"]:
            await self.events.send(
                channel, "level.up", level=update["level"], xp=update["xp"]
            )
        for id_ in update["new_achievements"]:
            title, description = ACHIEVEMENTS[id_]
            await self.events.send(
                channel,
                "achievement.unlocked",
                id=id_,
                title=title,
                description=description,
            )

    async def complete(
        self,
        lesson_id: str,
        user: User,
        answers: list[list[int]] | None = None,
    ) -> Document:
        async def save(tx: EducationData) -> Document:
            lesson, _ = await self.content.lesson(lesson_id, user, tx)
            at = now()
            errors: list[int] = []
            expected_type = "theory" if answers is None else "quiz"
            if lesson["type"] != expected_type:
                raise Problem(400, "lesson_type", "Действие недоступно для этого урока")
            if answers is not None:
                questions = lesson["questions"]
                if len(answers) > len(questions):
                    raise Problem(422, "answers", "Слишком много ответов")
                errors = [
                    index
                    for index, question in enumerate(questions)
                    if index >= len(answers)
                    or sorted(answers[index]) != sorted(question["correct"])
                ]
                await tx.add_quiz_attempt(
                    {
                        "user_id": user.id,
                        "lesson_id": lesson_id,
                        "answers": answers,
                        "errors": errors,
                        "submitted_at": at,
                    },
                )
            if errors:
                return {"passed": False, "errors": errors}
            profile = await tx.find_profile(user.id)
            assert profile is not None
            before = {
                "xp": profile["xp"],
                "achievements": profile.get("achievements", {}).copy(),
            }
            grant(profile, "lesson", lesson_id, LESSON_XP, at, user.timezone)
            await tx.save_profile(profile)
            return {"passed": True, "errors": [], **changes(before, profile)}

        result = await self.store.transaction(save)
        if result["passed"]:
            await self.notify(user.id, result)
        return result

    async def prize(self, event: Document) -> None:
        at = datetime.fromisoformat(event["finished_at"])
        for row in event["rows"]:
            xp = PLACE_XP.get(row["place"], 0)
            if not xp or not row["solved"]:
                continue

            async def save(
                tx: EducationData,
                row: Document = row,
                xp: int = xp,
            ) -> Document | None:
                profile = await tx.find_profile(row["id"])
                if profile is None:
                    profile = {
                        "id": row["id"],
                        "name": row["name"],
                        "timezone": "UTC",
                        "version": -1,
                        "active": True,
                        "xp": 0,
                        "sequence": 0,
                    }
                    await tx.add_profile(profile)
                if event["id"] in profile.get("prizes", {}):
                    return None
                before = {
                    "xp": profile["xp"],
                    "achievements": profile.get("achievements", {}).copy(),
                }
                grant(
                    profile,
                    "contest",
                    event["id"],
                    xp,
                    at,
                    winner=row["place"] == 1,
                )
                await tx.save_profile(profile)
                return changes(before, profile)

            update = await self.store.transaction(save)
            if update:
                await self.notify(row["id"], update)
                await self.events.send(
                    f"edu:user:{row['id']}",
                    "contest.reward",
                    id=event["id"],
                    place=row["place"],
                    xp=xp,
                )

    async def personal(self, user: User) -> Document:
        profile = await self.store.profile(user)
        current, best = streaks(profile.get("days", []))
        xp = profile["xp"]
        return {
            "id": user.id,
            "name": user.name,
            "xp": xp,
            "level": level(xp),
            "next_level_xp": 100 - xp % 100,
            "streak": current,
            "best_streak": best,
            "courses": profile.get("courses", []),
            "solved": len(profile.get("solved", {})),
            "achievements": [
                {
                    "id": id_,
                    "title": title,
                    "description": description,
                    "at": profile.get("achievements", {}).get(id_),
                }
                for id_, (title, description) in ACHIEVEMENTS.items()
            ],
        }

    async def topics(self, user: User) -> list[Document]:
        profile = await self.store.profile(user)
        completed = profile.get("completed", {})
        result = []
        async for course in self.store.enrolled_courses(profile.get("courses", [])):
            data = await self.content.structure(course["slug"], user)
            lessons = [
                lesson for module in data["modules"] for lesson in module["lessons"]
            ]
            topics = []
            for title in data["topics"]:
                ids = [lesson["id"] for lesson in lessons if lesson["topic"] == title]
                topics.append(
                    {
                        "title": title,
                        "percent": percent(
                            sum(id_ in completed for id_ in ids), len(ids)
                        ),
                    }
                )
            result.append(
                {"slug": data["slug"], "title": data["title"], "topics": topics}
            )
        return result

    async def gradebook(
        self, slug: str, user: User, offset: int = 0, *, export: bool = False
    ) -> Document:
        structure = await self.content.structure(slug, user, author=True)
        lessons = [
            lesson for module in structure["modules"] for lesson in module["lessons"]
        ]
        if not structure["published"]:
            lessons = []
        rows: list[Document] = []
        next_offset = None
        while True:
            profiles = [
                profile
                async for profile in self.store.course_profiles(slug, offset, 51)
            ]
            page = profiles[:50]
            attempted = await self.store.attempted_lessons(
                [profile["id"] for profile in page],
                [lesson["id"] for lesson in lessons],
                slug,
            )
            rows.extend(
                self.gradebook_row(
                    profile, lessons, attempted.get(profile["id"], set())
                )
                for profile in page
            )
            if len(profiles) <= 50:
                break
            offset += 50
            if not export:
                next_offset = offset
                break
        return {
            "columns": [
                {k: lesson[k] for k in ("id", "title", "type")} for lesson in lessons
            ],
            "rows": rows,
            "next_offset": next_offset,
        }

    @staticmethod
    def gradebook_row(
        profile: Document, lessons: list[Document], tried: set[str]
    ) -> Document:
        completed = profile.get("completed", {})
        task_xp_by_lesson: dict[str, int] = {}
        for award in profile.get("solved", {}).values():
            lesson_id = award.get("lesson_id")
            if lesson_id:
                task_xp_by_lesson[lesson_id] = (
                    task_xp_by_lesson.get(lesson_id, 0) + award["xp"]
                )
        cells = []
        for lesson in lessons:
            id_ = lesson["id"]
            status = (
                "completed"
                if id_ in completed
                else ("attempted" if id_ in tried else "unstarted")
            )
            cells.append(
                {
                    "lesson_id": id_,
                    "status": status,
                    "xp": completed.get(id_, {}).get("xp", 0),
                    "task_xp": task_xp_by_lesson.get(id_, 0),
                }
            )
        return {
            "id": profile["id"],
            "name": profile["name"],
            "cells": cells,
            "percent": percent(
                sum(cell["status"] == "completed" for cell in cells),
                len(lessons),
            ),
        }

    async def leaderboard(self, offset: int) -> list[Document]:
        return [
            {"id": row["id"], "name": row["name"], "xp": row["xp"], "rank": index}
            for index, row in enumerate(
                await self.store.ranked_profiles(offset), offset + 1
            )
        ]

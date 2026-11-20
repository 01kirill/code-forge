from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime

from pymongo import AsyncMongoClient, ReturnDocument
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.errors import DuplicateKeyError

from codeforge.common.contracts import Document, User
from codeforge.education.application.ports import DuplicateCourse, EducationData


def from_mongo(row: Document) -> Document:
    fields = {key: value for key, value in row.items() if key != "_id"}
    if "_id" in row:
        fields["id"] = row["_id"]
    return fields


def to_mongo(doc: Document) -> Document:
    return {key: value for key, value in doc.items() if key != "id"} | {
        "_id": doc["id"]
    }


class MongoEducationData:
    def __init__(
        self,
        client: AsyncMongoClient[Document],
        session: AsyncClientSession | None = None,
    ) -> None:
        self.client = client
        self.session = session
        db = client.education
        self._courses = db.courses
        self._lessons = db.lessons
        self._tasks = db.tasks
        self._submissions = db.submissions
        self._profiles = db.user_profiles
        self._quizzes = db.quiz_attempts
        self._judgements = db.judgements

    async def course(self, slug: str) -> Document | None:
        row = await self._courses.find_one(
            {"slug": slug, "archived": {"$ne": True}},
            session=self.session,
        )
        return from_mongo(row) if row is not None else None

    async def courses(
        self, *, published_only: bool, author: str | None, language: str | None
    ) -> list[Document]:
        query: Document = {"archived": {"$ne": True}}
        if published_only:
            query["published"] = True
        if author is not None:
            query["author_id"] = author
        if language:
            query["language"] = language
        return [
            from_mongo(row)
            async for row in self._courses.find(query, session=self.session)
            .sort("title")
            .limit(200)
        ]

    async def enrolled_courses(self, slugs: list[str]) -> AsyncIterator[Document]:
        async for row in self._courses.find(
            {"slug": {"$in": slugs}, "published": True},
            session=self.session,
        ).sort("title"):
            yield from_mongo(row)

    async def add_course(self, course: Document) -> None:
        try:
            await self._courses.insert_one(course, session=self.session)
        except DuplicateKeyError as exc:
            raise DuplicateCourse from exc

    async def update_course(self, slug: str, fields: Document) -> None:
        await self._courses.update_one(
            {"slug": slug}, {"$set": fields}, session=self.session
        )

    async def lesson(
        self, id_: str, *, include_archived: bool = False
    ) -> Document | None:
        query: Document = {"_id": id_}
        if not include_archived:
            query["archived"] = {"$ne": True}
        row = await self._lessons.find_one(query, session=self.session)
        return from_mongo(row) if row is not None else None

    async def lessons(
        self, ids: list[str], *, course: str | None = None
    ) -> list[Document]:
        query: Document = {"_id": {"$in": ids}, "archived": {"$ne": True}}
        if course is not None:
            query["course_slug"] = course
        return [
            from_mongo(row)
            async for row in self._lessons.find(query, session=self.session)
        ]

    async def set_module(self, lessons: list[str], module: int) -> None:
        await self._lessons.update_many(
            {"_id": {"$in": lessons}},
            {"$set": {"module": module}},
            session=self.session,
        )

    async def archive_lesson(self, id_: str) -> None:
        await self._lessons.update_one(
            {"_id": id_},
            {"$set": {"archived": True}},
            session=self.session,
        )

    async def add_lesson(self, lesson: Document) -> None:
        await self._lessons.insert_one(to_mongo(lesson), session=self.session)

    async def replace_lesson(self, lesson: Document) -> None:
        await self._lessons.replace_one(
            {"_id": lesson["id"]},
            to_mongo(lesson),
            session=self.session,
        )

    async def task(self, id_: str) -> Document | None:
        row = await self._tasks.find_one(
            {"task_id": id_, "current": True, "archived": {"$ne": True}},
            session=self.session,
        )
        return from_mongo(row) if row is not None else None

    async def task_version(self, id_: str, version: str) -> Document | None:
        row = await self._tasks.find_one(
            {"_id": version, "task_id": id_}, session=self.session
        )
        return from_mongo(row) if row is not None else None

    async def task_choices(
        self, *, contest: bool, author: str | None
    ) -> list[Document]:
        query: Document = {"current": True, "archived": {"$ne": True}}
        if contest:
            query["contest_ready"] = True
        elif author is not None:
            query["author_id"] = author
        fields = {"_id": 0, "task_id": 1, "title": 1, "difficulty": 1, "templates": 1}
        return [
            row
            async for row in self._tasks.find(query, fields, session=self.session)
            .sort("title")
            .limit(200)
        ]

    async def archive_task(self, version: str) -> None:
        await self._tasks.update_one(
            {"_id": version},
            {"$set": {"archived": True}},
            session=self.session,
        )

    async def retire_task_version(self, version: str) -> None:
        await self._tasks.update_one(
            {"_id": version},
            {"$set": {"current": False}},
            session=self.session,
        )

    async def has_lessons_for_task(self, task_id: str) -> bool:
        row = await self._lessons.find_one(
            {"task_id": task_id, "archived": {"$ne": True}},
            session=self.session,
        )
        return row is not None

    async def add_task(self, task: Document) -> None:
        await self._tasks.insert_one(to_mongo(task), session=self.session)

    async def add_quiz_attempt(self, submission: Document) -> None:
        await self._quizzes.insert_one(submission, session=self.session)

    async def attempted_quizzes(self, user: str, lessons: list[str]) -> list[str]:
        return await self._quizzes.distinct(
            "lesson_id",
            {"user_id": user, "lesson_id": {"$in": lessons}},
            session=self.session,
        )

    async def attempted_practice(self, user: str, course: str) -> list[str]:
        return await self._submissions.distinct(
            "lesson_id",
            {"user_id": user, "course_slug": course, "practice": False},
            session=self.session,
        )

    async def find_profile(self, user_id: str) -> Document | None:
        row = await self._profiles.find_one({"_id": user_id}, session=self.session)
        return from_mongo(row) if row is not None else None

    async def add_profile(self, profile: Document) -> None:
        await self._profiles.insert_one(to_mongo(profile), session=self.session)

    async def save_profile(self, profile: Document) -> None:
        await self._profiles.replace_one(
            {"_id": profile["id"]},
            to_mongo(profile),
            session=self.session,
        )

    async def enroll(self, user: str, slug: str) -> None:
        await self._profiles.update_one(
            {"_id": user},
            {"$addToSet": {"courses": slug}},
            session=self.session,
        )

    async def course_profiles(self, slug: str) -> AsyncIterator[Document]:
        async for row in self._profiles.find(
            {"courses": slug}, session=self.session
        ).sort([("name", 1), ("_id", 1)]):
            yield from_mongo(row)

    async def ranked_profiles(self, offset: int) -> list[Document]:
        return [
            from_mongo(row)
            async for row in self._profiles.find({"active": True}, session=self.session)
            .sort([("xp", -1), ("name", 1), ("_id", 1)])
            .skip(offset)
            .limit(50)
        ]

    async def next_sequence(self, user_id: str) -> int:
        row = await self._profiles.find_one_and_update(
            {"_id": user_id},
            {"$inc": {"sequence": 1}},
            return_document=ReturnDocument.AFTER,
            session=self.session,
        )
        assert row is not None
        return int(row["sequence"])

    async def profile_for_result(self, user_id: str) -> Document | None:
        # Force a transaction retry if two results update the same profile.
        row = await self._profiles.find_one_and_update(
            {"_id": user_id},
            {"$inc": {"result_revision": 1}},
            return_document=ReturnDocument.AFTER,
            session=self.session,
        )
        return from_mongo(row) if row is not None else None

    async def add_submission(self, attempt: Document) -> None:
        await self._submissions.insert_one(to_mongo(attempt), session=self.session)

    async def submission(self, id_: str, user_id: str) -> Document | None:
        row = await self._submissions.find_one(
            {"_id": id_, "user_id": user_id},
            session=self.session,
        )
        return from_mongo(row) if row is not None else None

    async def submissions(
        self, user: str, task: str | None, offset: int
    ) -> list[Document]:
        query: Document = {"user_id": user, "practice": False}
        if task:
            query["task_id"] = task
        return [
            from_mongo(row)
            async for row in self._submissions.find(query, session=self.session)
            .sort("sequence", -1)
            .skip(offset)
            .limit(30)
        ]

    async def task_history(self, user: str, task: str) -> AsyncIterator[Document]:
        async for row in self._submissions.find(
            {"user_id": user, "task_id": task, "practice": False},
            session=self.session,
        ).sort("sequence"):
            yield from_mongo(row)

    async def due_submissions(self, at: datetime) -> AsyncIterator[Document]:
        async for row in (
            self._submissions.find(
                {"state": "queued", "dispatch_after": {"$lte": at}},
                session=self.session,
            )
            .sort("dispatch_after")
            .limit(30)
        ):
            yield from_mongo(row)

    async def schedule_dispatch(
        self, id_: str, previous: datetime, next_at: datetime
    ) -> None:
        await self._submissions.update_one(
            {"_id": id_, "dispatch_after": previous},
            {"$set": {"dispatch_after": next_at}},
            session=self.session,
        )

    async def finish_submission(self, id_: str, result: Document) -> Document | None:
        row = await self._submissions.find_one_and_update(
            {"_id": id_, "state": "queued"},
            {"$set": {"state": "done", "result": result}},
            return_document=ReturnDocument.AFTER,
            session=self.session,
        )
        return from_mongo(row) if row is not None else None

    async def judgement(self, id_: str) -> Document | None:
        row = await self._judgements.find_one({"_id": id_}, session=self.session)
        return from_mongo(row) if row is not None else None

    async def claim(
        self, id_: str, lease: str, at: datetime, until: datetime
    ) -> Document | None:
        try:
            row = await self._judgements.find_one_and_update(
                {
                    "_id": id_,
                    "lease_until": {"$not": {"$gt": at}},
                    "result": {"$exists": False},
                },
                {
                    "$set": {"lease": lease, "lease_until": until},
                    "$setOnInsert": {"started_at": at},
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
                session=self.session,
            )
        except DuplicateKeyError:
            return None
        return from_mongo(row) if row is not None else None

    async def save_tokens(self, id_: str, lease: str, tokens: list[str]) -> None:
        await self._judgements.update_one(
            {"_id": id_, "lease": lease},
            {"$set": {"tokens": tokens}},
            session=self.session,
        )

    async def finish_judgement(self, id_: str, lease: str, result: Document) -> bool:
        update = await self._judgements.update_one(
            {"_id": id_, "lease": lease},
            {"$set": {"result": result}},
            session=self.session,
        )
        return bool(update.modified_count)


class MongoEducation(MongoEducationData):
    async def transaction[T](
        self, operation: Callable[[EducationData], Awaitable[T]]
    ) -> T:
        async def execute(session: AsyncClientSession) -> T:
            return await operation(MongoEducationData(self.client, session))

        async with self.client.start_session() as session:
            return await session.with_transaction(execute)

    async def initialize(self) -> None:
        await self._courses.create_index("slug", unique=True)
        await self._courses.create_index(
            [("published", 1), ("language", 1), ("title", 1)]
        )
        await self._lessons.create_index([("course_slug", 1), ("module", 1)])
        await self._tasks.create_index(
            "task_id",
            unique=True,
            partialFilterExpression={"current": True},
        )
        await self._submissions.create_index(
            [("user_id", 1), ("task_id", 1), ("sequence", -1)]
        )
        await self._submissions.create_index([("user_id", 1), ("sequence", -1)])
        await self._submissions.create_index([("state", 1), ("dispatch_after", 1)])
        await self._submissions.create_index("expires_at", expireAfterSeconds=0)
        await self._profiles.create_index([("active", 1), ("xp", -1), ("name", 1)])
        await self._profiles.create_index("courses")

    async def ensure_profile(self, user: User) -> None:
        profile = {
            "_id": user.id,
            "name": user.name,
            "timezone": user.timezone,
            "version": user.version,
            "active": True,
            "xp": 0,
            "sequence": 0,
        }
        await self._profiles.update_one(
            {"_id": user.id},
            {"$setOnInsert": profile},
            upsert=True,
        )

    async def profile(self, user: User) -> Document:
        profile = await self.find_profile(user.id)
        if profile is None:
            await self.ensure_profile(user)
            profile = await self.find_profile(user.id)
        assert profile is not None
        return profile

    async def sync_user(self, data: Document) -> None:
        identity = {key: data[key] for key in ("name", "timezone", "version", "active")}
        await self._profiles.update_one(
            {"_id": data["id"]},
            {
                "$setOnInsert": {
                    "version": -1,
                    "xp": 0,
                    "sequence": 0,
                }
            },
            upsert=True,
        )
        await self._profiles.update_one(
            {"_id": data["id"], "version": {"$lte": data["version"]}},
            {"$set": identity},
        )

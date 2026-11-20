from uuid import uuid4

from codeforge.common.contracts import Document, Problem, User, check_owner
from codeforge.education.application.ports import (
    CourseCache,
    CourseDraft,
    DuplicateCourse,
    EducationData,
    EducationRepository,
)
from codeforge.education.application.views import expose, now


def public_task(task: Document) -> Document:
    result = expose(task, "author_id", "tests", "current", "archived")
    result["examples"] = [test for test in task["tests"] if test["public"]]
    result["version"] = task["id"]
    return result


def require_teacher(user: User) -> None:
    if not user.teaches:
        raise Problem(403, "forbidden", "Недостаточно прав")


class Content:
    def __init__(self, store: EducationRepository, cache: CourseCache) -> None:
        self.store = store
        self.cache = cache

    async def course(self, slug: str, data: EducationData | None = None) -> Document:
        course = await (data or self.store).course(slug)
        if course is None:
            raise Problem(404, "course_missing", "Курс не найден")
        return course

    async def structure(
        self, slug: str, user: User | None, *, author: bool = False
    ) -> Document:
        course = await self.course(slug)
        if author:
            if user is None:
                raise Problem(401, "session", "Войдите в аккаунт")
            check_owner(user, course["author_id"])
        elif not course["published"]:
            raise Problem(404, "course_missing", "Курс не найден")
        revision = course["revision"]
        cached = None if author else await self.cache.get(slug, revision)
        if cached:
            result = cached
        else:
            ids = [id_ for module in course["modules"] for id_ in module["lessons"]]
            lessons = {lesson["id"]: lesson for lesson in await self.store.lessons(ids)}
            result = expose(course, "revision", "archived")
            result["updated_at"] = course["updated_at"].isoformat()
            result["modules"] = [
                {
                    "title": module["title"],
                    "lessons": [
                        (
                            expose(lessons[id_])
                            if author
                            else {
                                k: lessons[id_][k] for k in ("title", "type", "topic")
                            }
                        )
                        | {"id": id_}
                        for id_ in module["lessons"]
                        if id_ in lessons
                    ],
                }
                for module in course["modules"]
            ]
            if not author:
                await self.cache.save(slug, revision, result)
        if user:
            profile = await self.store.profile(user)
            result["enrolled"] = slug in profile.get("courses", [])
            result["completed"] = list(profile.get("completed", {}))
        return result

    async def list_courses(
        self,
        user: User | None,
        language: str | None,
        *,
        author: bool = False,
    ) -> list[Document]:
        owner = None
        if author:
            if user is None:
                raise Problem(403, "forbidden", "Недостаточно прав")
            require_teacher(user)
            if user.role != "admin":
                owner = user.id
        profile = await self.store.profile(user) if user else {}
        courses = await self.store.courses(
            published_only=not author,
            author=owner,
            language=language,
        )
        return [
            expose(course, "modules", "revision", "archived")
            | {
                "lesson_count": sum(
                    len(module["lessons"]) for module in course["modules"]
                ),
                "completed_count": sum(
                    id_ in profile.get("completed", {})
                    for module in course["modules"]
                    for id_ in module["lessons"]
                ),
                "enrolled": course["slug"] in profile.get("courses", []),
            }
            for course in courses
        ]

    async def mutate_course(
        self,
        slug: str,
        data: CourseDraft,
        user: User,
        *,
        create: bool = False,
    ) -> Document:
        require_teacher(user)

        async def save(tx: EducationData) -> str | None:
            old = None if create else await self.course(slug, tx)
            if old:
                check_owner(user, old["author_id"])
            ids = [id_ for module in data["modules"] for id_ in module["lessons"]]
            if ids:
                lessons = await tx.lessons(ids, course=slug)
                if len(lessons) != len(ids) or any(
                    lesson["topic"] not in data["topics"] for lesson in lessons
                ):
                    raise Problem(
                        422, "course_structure", "Проверьте темы и уроки курса"
                    )
                if data["published"]:
                    for lesson in lessons:
                        if lesson["type"] == "practice":
                            await self.task(lesson["task_id"], tx)
                for index, module in enumerate(data["modules"]):
                    await tx.set_module(module["lessons"], index)
            fields = dict(data) | {"updated_at": now(), "revision": uuid4().hex}
            if old:
                await tx.update_course(slug, fields)
            else:
                await tx.add_course(fields | {"slug": slug, "author_id": user.id})
            return old["revision"] if old else None

        try:
            revision = await self.store.transaction(save)
        except DuplicateCourse as exc:
            raise Problem(409, "duplicate_slug", "Такой адрес курса уже занят") from exc
        if revision:
            await self.cache.drop(slug, revision)
        return await self.structure(slug, user, author=True)

    async def delete_course(self, slug: str, user: User) -> None:
        async def archive(tx: EducationData) -> str:
            course = await self.course(slug, tx)
            check_owner(user, course["author_id"])
            await tx.update_course(slug, {"archived": True, "published": False})
            return str(course["revision"])

        revision = await self.store.transaction(archive)
        await self.cache.drop(slug, revision)

    async def enroll(self, slug: str, user: User) -> None:
        await self.store.ensure_profile(user)

        async def save(tx: EducationData) -> None:
            course = await self.course(slug, tx)
            if not course["published"]:
                raise Problem(404, "course_missing", "Курс не найден")
            await tx.enroll(user.id, slug)

        await self.store.transaction(save)

    async def task(self, id_: str, data: EducationData | None = None) -> Document:
        task = await (data or self.store).task(id_)
        if task is None:
            raise Problem(404, "task_missing", "Задача не найдена")
        return task

    async def list_tasks(self, user: User, *, contest: bool = False) -> list[Document]:
        owner = None
        if not contest:
            require_teacher(user)
            if user.role != "admin":
                owner = user.id
        return [
            expose(task, "templates") | {"languages": list(task["templates"])}
            for task in await self.store.task_choices(contest=contest, author=owner)
        ]

    async def author_task(self, id_: str, user: User) -> Document:
        task = await self.task(id_)
        check_owner(user, task["author_id"])
        return expose(task) | {"version": task["id"]}

    async def contest_task(self, id_: str) -> Document:
        task = await self.task(id_)
        if not task["contest_ready"]:
            raise Problem(404, "task_missing", "Задача недоступна для соревнований")
        return public_task(task)

    async def write_task(
        self, task_id: str | None, user: User, spec: Document
    ) -> Document:
        require_teacher(user)
        version = uuid4().hex
        stable_id = task_id or uuid4().hex

        async def save(tx: EducationData) -> Document:
            owner_id = user.id
            if task_id:
                old = await self.task(task_id, tx)
                owner_id = old["author_id"]
                check_owner(user, owner_id)
                await tx.retire_task_version(old["id"])
            task = spec | {
                "id": version,
                "task_id": stable_id,
                "author_id": owner_id,
                "current": True,
            }
            await tx.add_task(task)
            return expose(task) | {"version": version}

        return await self.store.transaction(save)

    async def delete_task(self, task_id: str, user: User) -> None:
        async def archive(tx: EducationData) -> None:
            task = await self.task(task_id, tx)
            check_owner(user, task["author_id"])
            if await tx.has_lessons_for_task(task_id):
                raise Problem(409, "task_in_use", "Сначала уберите задачу из уроков")
            await tx.archive_task(task["id"])

        await self.store.transaction(archive)

    async def lesson_slug(self, id_: str) -> str:
        lesson = await self.store.lesson(id_)
        if lesson is None:
            raise Problem(404, "lesson_missing", "Урок не найден")
        return str(lesson["course_slug"])

    async def lesson(
        self,
        lesson_id: str,
        user: User,
        data: EducationData | None = None,
    ) -> tuple[Document, Document]:
        reader = data or self.store
        doc = await reader.lesson(lesson_id)
        if doc is None:
            raise Problem(404, "lesson_missing", "Урок не найден")
        course = await self.course(doc["course_slug"], reader)
        if not course["published"] or not any(
            lesson_id in module["lessons"] for module in course["modules"]
        ):
            raise Problem(404, "lesson_missing", "Урок не найден")
        profile = await reader.find_profile(user.id)
        if profile is None or course["slug"] not in profile.get("courses", []):
            raise Problem(
                403,
                "enrollment",
                "Запишитесь на курс",
                course_slug=course["slug"],
            )
        return doc, course

    async def read_lesson(self, lesson_id: str, user: User) -> Document:
        doc, course = await self.lesson(lesson_id, user)
        result = expose(doc) | {
            "id": lesson_id,
            "course_title": course["title"],
            "course_language": course["language"],
        }
        profile = await self.store.profile(user)
        result["completed"] = lesson_id in profile.get("completed", {})
        if doc["type"] == "quiz":
            result["questions"] = [
                {k: v for k, v in question.items() if k != "correct"}
                for question in doc["questions"]
            ]
        if doc["type"] == "practice":
            result["task"] = public_task(await self.task(doc["task_id"]))
        return result

    async def write_lesson(
        self,
        slug: str,
        module: int | None,
        lesson: Document | None,
        user: User,
        lesson_id: str | None = None,
    ) -> Document:
        id_ = lesson_id or uuid4().hex

        async def save(tx: EducationData) -> str:
            course = await self.course(slug, tx)
            check_owner(user, course["author_id"])
            modules = course["modules"]
            if lesson is None:
                if course["published"] and sum(len(m["lessons"]) for m in modules) <= 1:
                    raise Problem(
                        409, "empty_course", "Сначала снимите курс с публикации"
                    )
                for group in modules:
                    group["lessons"] = [
                        item for item in group["lessons"] if item != id_
                    ]
                await tx.archive_lesson(id_)
            else:
                if lesson["topic"] not in course["topics"]:
                    raise Problem(422, "topic", "Выберите тему курса")
                if lesson["type"] == "practice":
                    task = await self.task(lesson["task_id"], tx)
                    check_owner(user, task["author_id"])
                fields = lesson | {"id": id_, "course_slug": slug}
                if lesson_id is None:
                    if module is None or module >= len(modules):
                        raise Problem(422, "module", "Выберите модуль курса")
                    await tx.add_lesson(fields | {"module": module})
                    modules[module]["lessons"].append(id_)
                else:
                    previous = await tx.lesson(id_, include_archived=True)
                    assert previous is not None
                    await tx.replace_lesson(fields | {"module": previous["module"]})
            await tx.update_course(
                slug,
                {
                    "modules": modules,
                    "revision": uuid4().hex,
                    "updated_at": now(),
                },
            )
            return str(course["revision"])

        revision = await self.store.transaction(save)
        await self.cache.drop(slug, revision)
        return {"id": id_}

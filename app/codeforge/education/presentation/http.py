import secrets
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Query, Request, Response, WebSocket

from codeforge.common.contracts import Document, Problem
from codeforge.common.http import ErrorResponse
from codeforge.common.runtime import socket_user, stream
from codeforge.common.security import CurrentUser, OptionalUser
from codeforge.education.application.content import Content
from codeforge.education.application.ports import CourseDraft, SubmissionDraft
from codeforge.education.application.progress import Progress
from codeforge.education.application.submissions import Submissions
from codeforge.education.presentation.csv_export import csv_gradebook
from codeforge.education.presentation.schemas import (
    Answers,
    CourseCreate,
    CourseEdit,
    Language,
    Lesson,
    LessonCreate,
    Run,
    Submission,
    TaskSpec,
)

internal = APIRouter()
router = APIRouter(
    prefix="/api/edu",
    responses={
        code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 429)
    },
)


def get_content(request: Request) -> Content:
    service: Content = request.app.state.content
    return service


def get_progress(request: Request) -> Progress:
    service: Progress = request.app.state.progress
    return service


def get_submissions(request: Request) -> Submissions:
    service: Submissions = request.app.state.submissions
    return service


Courses = Annotated[Content, Depends(get_content)]
Tracking = Annotated[Progress, Depends(get_progress)]
Attempts = Annotated[Submissions, Depends(get_submissions)]
Offset = Annotated[int, Query(ge=0, le=10000)]


@router.get("/courses")
async def courses(
    service: Courses,
    user: OptionalUser,
    language: Language | None = None,
) -> list[Document]:
    return await service.list_courses(user, language)


@router.get("/me/courses")
async def my_courses(service: Courses, user: CurrentUser) -> list[Document]:
    return await service.list_courses(user, None, author=True)


@router.get("/courses/{slug}")
async def course(
    slug: str,
    service: Courses,
    user: OptionalUser,
    author: bool = False,
) -> Document:
    return await service.structure(slug, user, author=author)


@router.post("/courses", status_code=201)
async def create_course(
    data: CourseCreate, service: Courses, user: CurrentUser
) -> Document:
    return await service.mutate_course(
        data.slug,
        cast(CourseDraft, data.model_dump(exclude={"slug"})),
        user,
        create=True,
    )


@router.patch("/courses/{slug}")
async def edit_course(
    slug: str,
    data: CourseEdit,
    service: Courses,
    user: CurrentUser,
) -> Document:
    return await service.mutate_course(slug, cast(CourseDraft, data.model_dump()), user)


@router.delete("/courses/{slug}", status_code=204)
async def delete_course(slug: str, service: Courses, user: CurrentUser) -> None:
    await service.delete_course(slug, user)


@router.post("/courses/{slug}/enroll", status_code=204)
async def enroll(slug: str, service: Courses, user: CurrentUser) -> None:
    await service.enroll(slug, user)


@router.get("/lessons/{lesson_id}")
async def lesson(lesson_id: str, service: Courses, user: CurrentUser) -> Document:
    return await service.read_lesson(lesson_id, user)


@router.post("/lessons", status_code=201)
async def create_lesson(
    data: LessonCreate, service: Courses, user: CurrentUser
) -> Document:
    return await service.write_lesson(
        data.course_slug, data.module, data.lesson.model_dump(), user
    )


@router.patch("/lessons/{lesson_id}")
async def edit_lesson(
    lesson_id: str,
    data: Lesson,
    service: Courses,
    user: CurrentUser,
) -> Document:
    slug = await service.lesson_slug(lesson_id)
    return await service.write_lesson(slug, None, data.model_dump(), user, lesson_id)


@router.delete("/lessons/{lesson_id}", status_code=204)
async def delete_lesson(lesson_id: str, service: Courses, user: CurrentUser) -> None:
    await service.write_lesson(
        await service.lesson_slug(lesson_id),
        None,
        None,
        user,
        lesson_id,
    )


@router.post("/lessons/{lesson_id}/complete")
async def complete(lesson_id: str, service: Tracking, user: CurrentUser) -> Document:
    return await service.complete(lesson_id, user)


@router.post("/lessons/{lesson_id}/quiz")
async def answers(
    lesson_id: str,
    data: Answers,
    service: Tracking,
    user: CurrentUser,
) -> Document:
    return await service.complete(lesson_id, user, data.answers)


@router.get("/tasks")
async def tasks(service: Courses, user: CurrentUser) -> list[Document]:
    return await service.list_tasks(user)


@router.get("/contest-tasks")
async def contest_tasks(service: Courses, user: CurrentUser) -> list[Document]:
    return await service.list_tasks(user, contest=True)


@router.get("/tasks/{task_id}")
async def author_task(task_id: str, service: Courses, user: CurrentUser) -> Document:
    return await service.author_task(task_id, user)


@router.post("/tasks", status_code=201)
async def create_task(data: TaskSpec, service: Courses, user: CurrentUser) -> Document:
    return await service.write_task(None, user, data.model_dump())


@router.patch("/tasks/{task_id}")
async def edit_task(
    task_id: str, data: TaskSpec, service: Courses, user: CurrentUser
) -> Document:
    return await service.write_task(task_id, user, data.model_dump())


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str, service: Courses, user: CurrentUser) -> None:
    await service.delete_task(task_id, user)


@internal.get("/internal/tasks/{task_id}/public", include_in_schema=False)
async def snapshot(
    task_id: str,
    service: Courses,
    request: Request,
    x_internal_key: Annotated[str, Header()] = "",
) -> Document:
    key: str = request.app.state.internal_key
    if not key or not secrets.compare_digest(x_internal_key.encode(), key.encode()):
        raise Problem(403, "forbidden", "Недостаточно прав")
    return await service.contest_task(task_id)


@router.post("/tasks/{task_id}/run", status_code=202)
async def run(
    task_id: str, data: Run, service: Attempts, user: CurrentUser
) -> Document:
    return await service.create(
        task_id,
        SubmissionDraft(data.lesson_id, data.language, data.code, True, data.stdin),
        user,
    )


@router.post("/tasks/{task_id}/submissions", status_code=202)
async def submit(
    task_id: str,
    data: Submission,
    service: Attempts,
    user: CurrentUser,
) -> Document:
    return await service.create(
        task_id,
        SubmissionDraft(data.lesson_id, data.language, data.code),
        user,
    )


@router.get("/tasks/{task_id}/submissions")
async def task_history(
    task_id: str,
    service: Attempts,
    user: CurrentUser,
    offset: Offset = 0,
) -> list[Document]:
    return await service.list(user, task_id, offset)


@router.get("/me/submissions")
async def history(
    service: Attempts, user: CurrentUser, offset: Offset = 0
) -> list[Document]:
    return await service.list(user, offset=offset)


@router.get("/submissions/{attempt_id}")
async def attempt(attempt_id: str, service: Attempts, user: CurrentUser) -> Document:
    return await service.get(attempt_id, user)


@router.get("/me/profile")
async def profile(service: Tracking, user: CurrentUser) -> Document:
    return await service.personal(user)


@router.get("/me/progress")
async def topics(service: Tracking, user: CurrentUser) -> list[Document]:
    return await service.topics(user)


@router.get("/leaderboard")
async def leaderboard(service: Tracking, offset: Offset = 0) -> list[Document]:
    return await service.leaderboard(offset)


@router.get("/courses/{slug}/gradebook", response_model=None)
async def gradebook(
    slug: str,
    service: Tracking,
    user: CurrentUser,
    format: str = "json",
) -> Document | Response:
    data = await service.gradebook(slug, user)
    if format == "csv":
        return Response(
            csv_gradebook(data),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{slug}.csv"',
                "Cache-Control": "private, no-store",
            },
        )
    return data


@internal.websocket("/ws/edu")
async def events(ws: WebSocket) -> None:
    try:
        user = await socket_user(ws)
    except Problem:
        await ws.close(code=4401)
        return
    await stream(ws, user, f"edu:user:{user.id}")

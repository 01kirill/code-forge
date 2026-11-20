from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, WebSocket

from codeforge.common.contracts import Document, Problem
from codeforge.common.http import ErrorResponse
from codeforge.common.runtime import socket_user, stream
from codeforge.common.security import CurrentUser
from codeforge.contest.application.ports import CodeSubmission, RoomDraft
from codeforge.contest.application.rooms import Contests
from codeforge.contest.presentation.schemas import ContestCode, Problems, RoomEdit

sockets = APIRouter()
router = APIRouter(
    prefix="/api/contest",
    responses={
        code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 429)
    },
)


def get_service(request: Request) -> Contests:
    contests: Contests = request.app.state.contests
    return contests


Service = Annotated[Contests, Depends(get_service)]


@router.get("/contests")
async def rooms(service: Service, user: CurrentUser) -> list[Document]:
    return await service.list_rooms(user)


@router.post("/contests", status_code=201)
async def create(data: RoomEdit, service: Service, user: CurrentUser) -> Document:
    return await service.create(
        RoomDraft(data.title, data.description, data.duration), user
    )


@router.post("/join/{token}")
async def join(
    token: Annotated[str, Path(pattern=r"^[\w-]{22}$")],
    service: Service,
    user: CurrentUser,
) -> Document:
    return await service.join(token, user)


@router.get("/contests/{id_}")
async def details(id_: UUID, service: Service, user: CurrentUser) -> Document:
    return await service.get(id_, user)


@router.patch("/contests/{id_}")
async def edit(
    id_: UUID, data: RoomEdit, service: Service, user: CurrentUser
) -> Document:
    return await service.edit(
        id_, RoomDraft(data.title, data.description, data.duration), user
    )


@router.put("/contests/{id_}/problems")
async def set_problems(
    id_: UUID, data: Problems, service: Service, user: CurrentUser
) -> Document:
    return await service.replace_problems(id_, data.task_ids, user)


@router.post("/contests/{id_}/invite")
async def invite(id_: UUID, service: Service, user: CurrentUser) -> Document:
    return await service.rotate_invite(id_, user)


@router.post("/contests/{id_}/start")
async def start(id_: UUID, service: Service, user: CurrentUser) -> Document:
    return await service.start(id_, user)


@router.get("/contests/{id_}/problems")
async def problems(id_: UUID, service: Service, user: CurrentUser) -> list[Document]:
    return await service.problems(id_, user)


@router.post("/contests/{id_}/problems/{label}/submissions", status_code=202)
async def submit(
    id_: UUID,
    label: Annotated[str, Path(pattern=r"^[A-Z]$")],
    data: ContestCode,
    service: Service,
    user: CurrentUser,
) -> Document:
    return await service.submit(
        id_, label, CodeSubmission(data.language, data.code), user
    )


@router.get("/contests/{id_}/submissions")
async def submissions(
    id_: UUID,
    service: Service,
    user: CurrentUser,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> list[Document]:
    return await service.submissions(id_, user, offset)


@router.get("/contests/{id_}/submissions/{attempt_id}")
async def attempt(
    id_: UUID, attempt_id: UUID, service: Service, user: CurrentUser
) -> Document:
    attempts = await service.submissions(id_, user, 0, attempt_id)
    if not attempts:
        raise Problem(404, "submission_missing", "Попытка не найдена")
    return attempts[0]


@router.get("/contests/{id_}/standings")
async def standings(id_: UUID, service: Service, user: CurrentUser) -> Document:
    return await service.standings(id_, user)


@sockets.websocket("/ws/contest/{id_}")
async def events(ws: WebSocket, id_: UUID) -> None:
    service: Contests = ws.app.state.contests
    try:
        user = await socket_user(ws)
        await service.check_membership(id_, user)
    except Problem:
        await ws.close(code=4401)
        return
    await stream(ws, user, f"contest:{id_}", f"contest:{id_}:user:{user.id}")

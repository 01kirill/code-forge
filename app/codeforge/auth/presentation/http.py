from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Request, Response

from codeforge.auth.application.accounts import REFRESH_DAYS, Accounts
from codeforge.auth.presentation.schemas import (
    AccessEdit,
    AccessToken,
    Login,
    ProfileEdit,
    Registration,
)
from codeforge.common.contracts import Document, Problem
from codeforge.common.http import ErrorResponse
from codeforge.common.security import CurrentUser, Tokens

COOKIE = "cf_refresh"


def response_cookie_secure(request: Request) -> bool:
    secure: bool = request.app.state.secure_cookie
    return secure


def set_session(
    request: Request, response: Response, pair: tuple[str, str]
) -> AccessToken:
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        COOKIE,
        pair[1],
        max_age=REFRESH_DAYS * 86400,
        httponly=True,
        secure=response_cookie_secure(request),
        samesite="strict",
        path="/api/auth",
    )
    return AccessToken(access_token=pair[0])


router = APIRouter(
    prefix="/api/auth",
    responses={
        code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 429)
    },
)


def accounts(request: Request) -> Accounts:
    service: Accounts = request.app.state.accounts
    return service


Service = Annotated[Accounts, Depends(accounts)]
RefreshCookie = Annotated[str | None, Cookie(alias=COOKIE, max_length=100)]


@router.post("/register", status_code=201)
async def register(data: Registration, request: Request, service: Service) -> Document:
    origin_check(request)
    ip = request.client.host if request.client else "unknown"
    user = await service.register(data.email, data.name, data.password, ip=ip)
    return {"id": user["id"], "name": user["name"]}


@router.post("/login")
async def login(
    data: Login,
    request: Request,
    response: Response,
    service: Service,
) -> AccessToken:
    origin_check(request)
    ip = request.client.host if request.client else "unknown"
    return set_session(
        request,
        response,
        await service.login(
            data.email,
            data.password,
            ip,
            request.headers.get("user-agent", ""),
        ),
    )


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    service: Service,
    token: RefreshCookie = None,
) -> AccessToken:
    origin_check(request)
    if not token:
        raise Problem(401, "session", "Войдите в аккаунт")
    return set_session(
        request,
        response,
        await service.rotate(
            token,
            request.headers.get("user-agent", ""),
        ),
    )


def origin_check(request: Request) -> None:
    origin = request.headers.get("origin")
    if (origin and origin != str(request.base_url).rstrip("/")) or (
        request.headers.get("sec-fetch-site") in {"cross-site", "same-site"}
    ):
        raise Problem(403, "forbidden", "Недопустимый источник запроса")


@router.post("/socket-ticket")
async def socket_ticket(
    request: Request, response: Response, user: CurrentUser
) -> Document:
    tokens: Tokens = request.app.state.tokens
    response.headers["Cache-Control"] = "no-store"
    return {"ticket": await tokens.socket_ticket(user)}


@router.post("/logout", status_code=204)
async def logout(
    request: Request, response: Response, user: CurrentUser, service: Service
) -> None:
    await service.logout(user)
    response.delete_cookie(
        COOKIE,
        path="/api/auth",
        secure=response_cookie_secure(request),
        httponly=True,
        samesite="strict",
    )


@router.get("/me")
async def me(user: CurrentUser, service: Service) -> Document:
    return await service.me(user)


@router.patch("/me")
async def edit_profile(
    data: ProfileEdit, user: CurrentUser, service: Service
) -> Document:
    return await service.update_profile(user, data.name, data.timezone)


@router.get("/users")
async def users(user: CurrentUser, service: Service, q: str = "") -> list[Document]:
    return await service.search(user, q)


@router.get("/users/{user_id}")
async def public_user(user_id: UUID, service: Service) -> Document:
    return await service.public_user(user_id)


@router.patch("/users/{user_id}/role")
async def change_access(
    user_id: UUID,
    data: AccessEdit,
    user: CurrentUser,
    service: Service,
) -> Document:
    return await service.change_access(user, user_id, data.role, data.active)

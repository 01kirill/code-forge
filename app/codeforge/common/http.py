import logging
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from codeforge.common.contracts import Problem as Problem

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    detail: str
    code: str
    errors: list[dict[str, str]] | None = None
    context: dict[str, str] | None = None


def application(name: str, lifespan: Callable[..., Any]) -> FastAPI:
    app = FastAPI(title=f"CodeForge {name}", lifespan=lifespan)

    @app.exception_handler(Problem)
    async def problem_response(request: Request, exc: Problem) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={
                "detail": exc.detail,
                "code": exc.code,
                **({"context": exc.context} if exc.context else {}),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_response(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Проверьте заполнение полей",
                "code": "validation",
                "errors": [
                    {"field": ".".join(map(str, e["loc"][1:])), "type": e["type"]}
                    for e in exc.errors()
                ],
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Request failed: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"detail": "Сервис временно недоступен", "code": "unavailable"},
        )

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


type BackgroundJob = Callable[[], Coroutine[Any, Any, None]]

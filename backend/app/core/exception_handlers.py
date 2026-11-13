
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIException(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        fields: list[dict[str, str]] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields or []


async def api_exception_handler(
    request: Request,
    exc: APIException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "fields": exc.fields,
            }
        },
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    field_errors = []

    for error in exc.errors():
        location = [
            str(part)
            for part in error.get("loc", [])
            if part not in ("body", "query", "path")
        ]

        field_errors.append({
            "field": ".".join(location) or "request",
            "message": error.get("msg", "Invalid value"),
            "code": error.get("type", "validation_error"),
        })

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Please correct the invalid request fields.",
                "fields": field_errors,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )

    app.add_exception_handler(
        APIException,
        api_exception_handler,
    )

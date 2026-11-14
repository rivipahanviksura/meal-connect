
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


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

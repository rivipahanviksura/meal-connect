
from fastapi import FastAPI, Request, HTTPException
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


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    if exc.status_code == 401:
        error_code = "AUTH_REQUIRED"
        message = "Authentication required"

    elif exc.status_code == 403:
        error_code = "FORBIDDEN"
        message = "Permission denied"

    elif exc.status_code == 404:
        error_code = "NOT_FOUND"
        message = "Resource not found"

    elif exc.status_code == 409:
        allowed_codes = {
            "ALREADY_EXISTS",
            "QUANTITY_CONFLICT",
            "DONATION_EXPIRED",
            "INVALID_STATE_TRANSITION",
        }

        error_code = (
            exc.detail
            if isinstance(exc.detail, str) and exc.detail in allowed_codes
            else "INVALID_STATE_TRANSITION"
        )

        message = "The requested operation conflicts with the current state"

    else:
        error_code = (
            "INTERNAL_ERROR"
            if exc.status_code >= 500
            else "HTTP_ERROR"
        )
        message = "Request could not be completed"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": error_code,
                "message": message,
                "fields": [],
            }
        },
        headers=exc.headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )

    app.add_exception_handler(
        HTTPException,
        http_exception_handler,
    )

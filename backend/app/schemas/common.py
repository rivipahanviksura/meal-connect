
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, Field


def reject_null_character(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Text cannot contain a null character.")
    return value


# PostgreSQL text and varchar cannot store a zero byte.
DatabaseText = Annotated[str, AfterValidator(reject_null_character)]


class FieldError(BaseModel):
    field: str
    message: str
    code: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: list[FieldError] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class MessageResponse(BaseModel):
    message: str


class DataResponse(BaseModel):
    data: dict[str, Any]

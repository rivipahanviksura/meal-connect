
from typing import Any

from pydantic import BaseModel, Field


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

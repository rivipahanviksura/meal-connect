from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AdminApproveRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    comment: str | None = Field(
        default=None,
        max_length=2000,
    )


class AdminRejectRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    reason: str = Field(
        min_length=10,
        max_length=2000,
    )


class AdminCorrectionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    reason: str = Field(
        min_length=10,
        max_length=2000,
    )


class AdminDecisionData(BaseModel):
    application_id: int
    organization_id: int

    action: Literal[
        "approve",
        "reject",
        "request_corrections",
    ]

    status: Literal[
        "verified",
        "rejected",
    ]

    reviewed_by_user_id: int
    reviewed_at: datetime
    reason: str | None = None


class AdminDecisionResponse(BaseModel):
    data: AdminDecisionData


class AdminDecisionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    decision: Literal[
        "approved",
        "rejected",
        "request_corrections",
    ]

    review_note: str = Field(
        min_length=10,
        max_length=2000,
    )

    @model_validator(mode="after")
    def validate_review_note(self):
        if not self.review_note.strip():
            raise ValueError("Review note is required.")
        return self


class AdminDocumentReviewRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    decision: Literal["approved", "rejected"]
    review_note: str = Field(min_length=10, max_length=2000)


class AdminDocumentReviewData(BaseModel):
    application_id: int
    document_id: int
    review_status: Literal["approved", "rejected"]
    reviewed_by_user_id: int
    reviewed_at: datetime
    review_note: str


class AdminDocumentReviewResponse(BaseModel):
    data: AdminDocumentReviewData

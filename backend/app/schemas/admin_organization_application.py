from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


POSTGRES_MAX_OFFSET = (2**63) - 1

AdminOrganizationType = Literal["restaurant", "bakery", "ngo"]
AdminVerificationStatus = Literal["pending", "approved", "rejected", "suspended"]


class AdminApplicationQueueQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    organization_type: AdminOrganizationType | None = None
    status: AdminVerificationStatus = "pending"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_pagination_offset(self) -> Self:
        offset = (self.page - 1) * self.page_size

        if offset > POSTGRES_MAX_OFFSET:
            raise ValueError(
                "The requested page and page_size exceed "
                "the supported pagination range."
            )

        return self


class AdminApplicationQueueItem(BaseModel):
    application_id: int
    organization_id: int
    organization_name: str
    organization_type: AdminOrganizationType
    registration_number: str | None
    submitted_at: datetime
    verification_status: AdminVerificationStatus


class AdminApplicationPagination(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class AdminApplicationQueueResponse(BaseModel):
    data: list[AdminApplicationQueueItem]
    pagination: AdminApplicationPagination


class AdminApplicationDocument(BaseModel):
    document_id: int
    document_type: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    review_status: str
    uploaded_at: datetime


class AdminApplicationSubmissionHistory(BaseModel):
    submission_id: int
    submitted_at: datetime
    snapshot: dict


class AdminApplicationReviewHistory(BaseModel):
    verification_id: int
    decision: AdminVerificationStatus
    review_note: str | None
    reviewed_at: datetime
    reviewer_name: str | None = None


class AdminApplicationStatusHistory(BaseModel):
    status_history_id: int
    old_status: str | None
    new_status: str
    change_reason: str | None
    changed_at: datetime
    changed_by_name: str | None = None


class AdminApplicationDetail(BaseModel):
    application_id: int
    organization_id: int
    name: str
    organization_type: AdminOrganizationType
    registration_number: str | None
    contact_email: str
    contact_phone: str | None
    address_line: str
    city: str
    district: str | None
    registration_authority: str | None
    registration_date: date | None
    registration_expiry_date: date | None
    representative_name: str | None
    representative_designation: str | None
    pickup_location: str | None
    operational_details: dict | None
    submitted_at: datetime | None
    verification_status: AdminVerificationStatus
    documents: list[AdminApplicationDocument]
    submissions: list[AdminApplicationSubmissionHistory]
    reviews: list[AdminApplicationReviewHistory]
    status_history: list[AdminApplicationStatusHistory]


class AdminApplicationDetailResponse(BaseModel):
    data: AdminApplicationDetail

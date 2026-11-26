
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ApplicationDetails(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str = Field(min_length=1, max_length=180)
    registration_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    contact_email: Annotated[EmailStr, Field(max_length=255)]
    contact_phone: str | None = Field(
        default=None,
        min_length=1,
        max_length=25,
    )
    address_line: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=120)
    district: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )
    representative_name: str = Field(min_length=1, max_length=180)
    representative_designation: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


class BusinessApplication(ApplicationDetails):
    organization_type: Literal["business"]
    business_subtype: Literal["restaurant", "bakery"]
    pickup_location: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )


class NgoOperationalDetails(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    operating_area: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    distribution_area: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    operational_capability: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )


class NgoApplication(ApplicationDetails):
    organization_type: Literal["ngo"]
    registration_authority: str | None = Field(
        default=None,
        min_length=1,
        max_length=180,
    )
    registration_date: date | None = None
    operational_details: NgoOperationalDetails | None = None

    @field_validator("registration_date")
    @classmethod
    def validate_registration_date(
        cls,
        value: date | None,
    ) -> date | None:
        if value is not None and value > date.today():
            raise ValueError(
                "Registration date cannot be in the future"
            )
        return value


ApplicationRequest = Annotated[
    BusinessApplication | NgoApplication,
    Field(discriminator="organization_type"),
]


class ApplicationDraft(BaseModel):
    application_id: int
    organization_id: int
    status: Literal["draft"] = "draft"


class ApplicationDraftResponse(BaseModel):
    data: ApplicationDraft


class ApplicationSummary(BaseModel):
    application_id: int
    organization_id: int
    name: str
    status: Literal[
        "draft",
        "pending_verification",
        "verified",
        "rejected",
        "suspended",
    ]
    review_note: str | None = None
    draft_details: ApplicationRequest | None = None


class ApplicationPagination(BaseModel):
    page: Literal[1] = 1
    page_size: Literal[20] = 20
    total_items: Literal[0, 1]
    total_pages: Literal[0, 1]


class ApplicationListResponse(BaseModel):
    data: list[ApplicationSummary]
    pagination: ApplicationPagination


# MEAL-13: Supported organization verification documents.
DocumentType = Literal[
    "registration_certificate",
    "representative_authorization",
    "supporting_document",
    "food_premises_certificate",
    "trade_licence",
]


class ApplicationDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: int
    document_type: DocumentType
    content_type: str
    file_size_bytes: int


class ApplicationDocumentResponse(BaseModel):
    data: ApplicationDocument


class ApplicationSubmitted(BaseModel):
    application_id: int
    organization_id: int
    status: Literal["pending_verification"] = "pending_verification"


class ApplicationSubmittedResponse(BaseModel):
    data: ApplicationSubmitted

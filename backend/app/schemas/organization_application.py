from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ApplicationDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=180)
    registration_number: str | None = Field(default=None, min_length=1, max_length=100)
    contact_email: Annotated[EmailStr, Field(max_length=255)]
    contact_phone: str | None = Field(default=None, min_length=1, max_length=25)
    address_line: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=120)
    district: str | None = Field(default=None, min_length=1, max_length=120)
    representative_name: str = Field(min_length=1, max_length=180)


class BusinessApplication(ApplicationDetails):
    organization_type: Literal["business"]
    business_subtype: Literal["restaurant", "bakery"]


class NgoApplication(ApplicationDetails):
    organization_type: Literal["ngo"]


ApplicationRequest = Annotated[
    BusinessApplication | NgoApplication, Field(discriminator="organization_type")
]


class ApplicationDraft(BaseModel):
    application_id: int
    organization_id: int
    status: Literal["draft"] = "draft"

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.db.models.donation import DonationStatus


class DonationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    organization_id: int | None = Field(default=None, gt=0)
    status: Literal["draft", "available"] = "draft"
    title: str = Field(min_length=1, max_length=180)
    category: str = Field(min_length=1, max_length=100)
    description: str | None = None

    total_quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    quantity_unit: str = Field(min_length=1, max_length=30)

    allergen_info: str | None = None
    storage_instructions: str | None = None

    prepared_at: AwareDatetime | None = None
    available_from: AwareDatetime
    pickup_deadline: AwareDatetime

    pickup_address: str = Field(min_length=1, max_length=255)
    pickup_city: str = Field(min_length=1, max_length=120)

    @field_validator("prepared_at", "available_from", "pickup_deadline", mode="before")
    @classmethod
    def parse_iso_datetime(cls, value: object) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise ValueError("Use an ISO 8601 datetime with a timezone offset.")

    @model_validator(mode="after")
    def validate_timestamps(self):
        available_from_utc = self.available_from.astimezone(timezone.utc)
        pickup_deadline_utc = self.pickup_deadline.astimezone(timezone.utc)

        if pickup_deadline_utc <= available_from_utc:
            raise ValueError(
                "Pickup deadline must be after available from."
            )

        if self.prepared_at is not None:
            prepared_at_utc = self.prepared_at.astimezone(timezone.utc)

            if prepared_at_utc > pickup_deadline_utc:
                raise ValueError(
                    "Prepared time cannot be after pickup deadline."
                )

        return self


class DonationResponseData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    donation_id: int
    organization_id: int
    created_by_user_id: int
    title: str
    category: str
    description: str | None
    total_quantity: Decimal
    allocated_quantity: Decimal
    quantity_unit: str
    allergen_info: str | None
    storage_instructions: str | None
    prepared_at: datetime | None
    available_from: datetime
    pickup_deadline: datetime
    pickup_address: str
    pickup_city: str
    status: DonationStatus
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        "prepared_at", "available_from", "pickup_deadline", "created_at", "updated_at",
        when_used="json",
    )
    def serialize_utc(self, value: datetime | None) -> datetime | None:
        return None if value is None else value.astimezone(timezone.utc)


class DonationResponse(BaseModel):
    data: DonationResponseData

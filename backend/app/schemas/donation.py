from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
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

class DonationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = None
    category: str | None = None
    description: str | None = None
    total_quantity: Decimal | None = None
    quantity_unit: str | None = None
    allergen_info: str | None = None
    storage_instructions: str | None = None
    prepared_at: AwareDatetime | None = None
    available_from: AwareDatetime | None = None
    pickup_deadline: AwareDatetime | None = None
    pickup_address: str | None = None
    pickup_city: str | None = None

    @field_validator("prepared_at", "available_from", "pickup_deadline", mode="before")
    @classmethod
    def parse_iso_datetime(cls, value: object) -> datetime | None:
        return DonationCreate.parse_iso_datetime(value)


class DonationCancellation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str | None = Field(default=None, max_length=1000)

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


POSTGRES_MAX_OFFSET = (2**63) - 1


class DonationBrowseQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    city: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    category: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    status: Literal["available", "partially_allocated"] | None = None

    min_quantity: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=12,
        decimal_places=2,
    )

    available_before: AwareDatetime | None = None

    sort: Literal[
        "pickup_deadline",
        "-pickup_deadline",
        "created_at",
        "-created_at",
    ] = "pickup_deadline"

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


class DonationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    donation_id: int
    organization_id: int
    title: str
    category: str
    description: str | None
    allergen_info: str | None
    storage_instructions: str | None
    prepared_at: datetime | None

    total_quantity: Decimal
    allocated_quantity: Decimal
    quantity_unit: str

    available_from: datetime
    pickup_deadline: datetime
    pickup_address: str
    pickup_city: str
    created_at: datetime

    status: Literal["available", "partially_allocated"]

    @computed_field
    @property
    def remaining_quantity(self) -> Decimal:
        return self.total_quantity - self.allocated_quantity

    @field_serializer(
        "prepared_at", "available_from", "pickup_deadline", "created_at", when_used="json",
    )
    def serialize_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class DonationPagination(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class DonationListResponse(BaseModel):
    data: list[DonationListItem]
    pagination: DonationPagination

class DonationDetailData(BaseModel):
    """Donation details returned to authorized users."""

    model_config = ConfigDict(from_attributes=True)

    donation_id: int
    organization_id: int

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

    @computed_field
    @property
    def remaining_quantity(self) -> Decimal:
        return self.total_quantity - self.allocated_quantity

    @field_serializer(
        "prepared_at",
        "available_from",
        "pickup_deadline",
        "created_at",
        "updated_at",
        when_used="json",
    )
    def serialize_utc(
        self, value: datetime | None
    ) -> datetime | None:
        if value is None:
            return None

        if value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)


class DonationDetailResponse(BaseModel):
    data: DonationDetailData

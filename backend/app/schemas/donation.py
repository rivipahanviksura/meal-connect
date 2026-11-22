from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BeforeValidator,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    model_validator,
)

from app.core.timezone import to_utc
from app.db.models.donation import DonationStatus
from app.schemas.common import DatabaseText


def parse_donation_timestamp(value: object) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise ValueError("Use an ISO 8601 datetime with a timezone offset.")


def normalize_donation_timestamp(value: datetime) -> datetime:
    try:
        return to_utc(value)
    except OverflowError:
        raise ValueError("Timestamp is outside the supported UTC range.") from None


DonationTimestamp = Annotated[
    AwareDatetime,
    BeforeValidator(parse_donation_timestamp),
    AfterValidator(normalize_donation_timestamp),
]


class DonationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    organization_id: int | None = Field(default=None, strict=True, gt=0, le=2**63 - 1)
    status: Literal["draft", "available"] = "draft"
    title: DatabaseText = Field(min_length=1, max_length=180)
    category: DatabaseText = Field(min_length=1, max_length=100)
    description: DatabaseText | None = None

    total_quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    quantity_unit: DatabaseText = Field(min_length=1, max_length=30)

    allergen_info: DatabaseText | None = None
    storage_instructions: DatabaseText | None = None

    prepared_at: DonationTimestamp | None = None
    available_from: DonationTimestamp
    pickup_deadline: DonationTimestamp

    pickup_address: DatabaseText = Field(min_length=1, max_length=255)
    pickup_city: DatabaseText = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_timestamps(self):
        if self.pickup_deadline <= self.available_from:
            raise ValueError("Pickup deadline must be after available from.")

        if self.prepared_at is not None and self.prepared_at > self.pickup_deadline:
            raise ValueError("Prepared time cannot be after pickup deadline.")

        return self


class DonationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: DatabaseText | None = None
    category: DatabaseText | None = None
    description: DatabaseText | None = None
    total_quantity: Decimal | None = None
    quantity_unit: DatabaseText | None = None
    allergen_info: DatabaseText | None = None
    storage_instructions: DatabaseText | None = None
    prepared_at: DonationTimestamp | None = None
    available_from: DonationTimestamp | None = None
    pickup_deadline: DonationTimestamp | None = None
    pickup_address: DatabaseText | None = None
    pickup_city: DatabaseText | None = None


class DonationCancellation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: DatabaseText | None = Field(default=None, max_length=1000)


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

    city: DatabaseText | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    category: DatabaseText | None = Field(
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

    available_before: DonationTimestamp | None = None

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

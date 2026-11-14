from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


POSTGRES_MAX_OFFSET = (2**63) - 1


class DonationBrowseQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

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

    total_quantity: Decimal
    allocated_quantity: Decimal
    remaining_quantity: Decimal
    quantity_unit: str

    available_from: datetime
    pickup_deadline: datetime
    pickup_city: str

    status: Literal["available", "partially_allocated"]


class DonationPagination(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class DonationListResponse(BaseModel):
    data: list[DonationListItem]
    pagination: DonationPagination
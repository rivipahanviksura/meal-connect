import pytest
from pydantic import ValidationError

from app.schemas.donation import (
    POSTGRES_MAX_OFFSET,
    DonationBrowseQuery,
)


def test_default_pagination_is_valid():
    filters = DonationBrowseQuery()

    assert filters.page == 1
    assert filters.page_size == 20


def test_exact_maximum_offset_is_allowed():
    filters = DonationBrowseQuery(
        page=POSTGRES_MAX_OFFSET + 1,
        page_size=1,
    )

    offset = (filters.page - 1) * filters.page_size

    assert offset == POSTGRES_MAX_OFFSET


def test_offset_above_maximum_is_rejected():
    with pytest.raises(
        ValidationError,
        match="supported pagination range",
    ):
        DonationBrowseQuery(
            page=POSTGRES_MAX_OFFSET + 2,
            page_size=1,
        )


@pytest.mark.parametrize("page_size", [20, 100])
def test_largest_safe_page_for_page_size_is_allowed(page_size):
    largest_safe_page = POSTGRES_MAX_OFFSET // page_size + 1

    filters = DonationBrowseQuery(
        page=largest_safe_page,
        page_size=page_size,
    )

    assert (
        (filters.page - 1) * filters.page_size
        <= POSTGRES_MAX_OFFSET
    )


@pytest.mark.parametrize("page_size", [20, 100])
def test_first_unsafe_page_for_page_size_is_rejected(page_size):
    first_unsafe_page = POSTGRES_MAX_OFFSET // page_size + 2

    with pytest.raises(
        ValidationError,
        match="supported pagination range",
    ):
        DonationBrowseQuery(
            page=first_unsafe_page,
            page_size=page_size,
        )


@pytest.mark.parametrize(
    "values",
    [
        {"page": 0},
        {"page": -1},
        {"page_size": 0},
        {"page_size": 101},
    ],
)
def test_invalid_pagination_bounds_are_rejected(values):
    with pytest.raises(ValidationError):
        DonationBrowseQuery(**values)
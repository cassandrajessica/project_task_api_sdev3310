"""Unit tests for every Book Pydantic schema and declared rule."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.models.book import Book
from app.schemas.books import CURRENT_YEAR, BookInput, BookResponse


@pytest.mark.parametrize(
    "missing_field",
    ["title", "author", "isbn", "published_year", "member_id"],
)
def test_book_create_requires_each_declared_field(missing_field: str) -> None:
    """A create request must include every Book field."""
    data = valid_book_data()
    data.pop(missing_field)

    with pytest.raises(ValidationError):
        BookInput(**data)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("title", "   "),
        ("title", "t" * 201),
        ("author", "   "),
        ("author", "a" * 121),
        ("isbn", "   "),
        ("isbn", "9" * 21),
        ("published_year", 1449),
        ("published_year", CURRENT_YEAR + 1),
        ("member_id", 0),
    ],
    ids=[
        "blank-title",
        "title-over-maximum",
        "blank-author",
        "author-over-maximum",
        "blank-isbn",
        "isbn-over-maximum",
        "year-before-minimum",
        "year-after-current-year",
        "nonpositive-member-id",
    ],
)
def test_book_create_enforces_field_boundaries(
    field_name: str,
    value: Any,
) -> None:
    """Book fields must satisfy their declared constraints."""
    data = valid_book_data()
    data[field_name] = value

    with pytest.raises(ValidationError):
        BookInput(**data)


def test_book_create_accepts_declared_boundary_values() -> None:
    """The inclusive minimum and maximum values remain valid request values."""
    book = BookInput(
        title="t" * 200,
        author="a" * 120,
        isbn="9" * 20,
        published_year=1450,
        member_id=1,
    )

    assert len(book.title) == 200
    assert len(book.author) == 120
    assert len(book.isbn) == 20
    assert book.published_year == 1450


def test_book_create_accepts_the_current_year() -> None:
    """The published-year upper bound includes the current year."""
    data = valid_book_data()
    data["published_year"] = CURRENT_YEAR

    assert BookInput(**data).published_year == CURRENT_YEAR


def test_book_create_strips_surrounding_whitespace() -> None:
    """Shared schema configuration normalizes string input."""
    book = BookInput(
        title="  The Pragmatic Programmer  ",
        author="  Andrew Hunt  ",
        isbn="  978-0135957059  ",
        published_year=2019,
        member_id=1,
    )

    assert book.title == "The Pragmatic Programmer"
    assert book.author == "Andrew Hunt"
    assert book.isbn == "978-0135957059"


def test_book_create_rejects_undocumented_field() -> None:
    """The request contract rejects input outside the documented schema."""
    with pytest.raises(ValidationError):
        BookInput(**valid_book_data(), genre="Software")


def test_book_response_reads_an_orm_book() -> None:
    """The response schema serializes attributes from an ORM model instance."""
    source = Book(id=1, **valid_book_data())

    response = BookResponse.model_validate(source)

    assert response.model_dump() == {**valid_book_data(), "id": 1}


def test_book_response_rejects_nonpositive_server_id() -> None:
    """A response must contain a positive server-generated identifier."""
    with pytest.raises(ValidationError):
        BookResponse(**valid_book_data(), id=0)


# HELPERS


def valid_book_data() -> dict[str, Any]:
    """Return a valid Book request body for focused validation scenarios."""
    return {
        "title": "The Pragmatic Programmer",
        "author": "Andrew Hunt",
        "isbn": "978-0135957059",
        "published_year": 2019,
        "member_id": 1,
    }

"""Unit tests for the in-memory Book service contract."""

import pytest

from app.exceptions import (
    BookNotFoundError,
    IsbnAlreadyExistsError,
    MemberNotFoundError,
)
from app.models.member import Member
from app.schemas.books import BookInput
from app.services.books import InMemoryBookService
from app.services.in_memory_store import InMemoryStore


@pytest.fixture
def store() -> InMemoryStore:
    # Start with one Member and no Books. Book rules need an existing parent
    # Member, while an empty Book list keeps every expected ID explicit.
    return InMemoryStore(
        members=[
            Member(
                id=1,
                name="Ada Lovelace",
                email="ada@example.com",
                membership_id="LIB-1",
                phone="555-123-4567",
            )
        ],
        books=[],
    )


@pytest.fixture
def service(store: InMemoryStore) -> InMemoryBookService:
    return InMemoryBookService(store)


def book_data(isbn: str = "978-0135957059", member_id: int = 1) -> BookInput:
    return BookInput(
        title="The Pragmatic Programmer",
        author="Andrew Hunt",
        isbn=isbn,
        published_year=2019,
        member_id=member_id,
    )


def test_create_list_and_get_book(service: InMemoryBookService) -> None:
    created = service.create_book(book_data())

    assert created.id == 1
    assert service.list_books() == [created]
    assert service.get_book(created.id) is created


def test_get_book_raises_for_missing_id(service: InMemoryBookService) -> None:
    with pytest.raises(BookNotFoundError):
        service.get_book(999)


def test_create_book_requires_existing_member(service: InMemoryBookService) -> None:
    with pytest.raises(MemberNotFoundError):
        service.create_book(book_data(member_id=999))

    assert service.list_books() == []


def test_create_book_rejects_duplicate_isbn(service: InMemoryBookService) -> None:
    service.create_book(book_data())

    with pytest.raises(IsbnAlreadyExistsError):
        service.create_book(book_data())

    assert len(service.list_books()) == 1


def test_replace_book_updates_fields(service: InMemoryBookService) -> None:
    book = service.create_book(book_data())

    updated = service.replace_book(
        book.id,
        BookInput(
            title="Clean Code",
            author="Robert C. Martin",
            isbn="978-0132350884",
            published_year=2008,
            member_id=1,
        ),
    )

    assert updated is book
    assert updated.title == "Clean Code"
    assert updated.isbn == "978-0132350884"
    assert updated.published_year == 2008


def test_replace_book_keeps_its_own_isbn(service: InMemoryBookService) -> None:
    book = service.create_book(book_data())

    updated = service.replace_book(book.id, book_data())

    assert updated.isbn == "978-0135957059"


def test_replace_book_rejects_missing_member_without_changes(
    service: InMemoryBookService,
) -> None:
    book = service.create_book(book_data())

    with pytest.raises(MemberNotFoundError):
        service.replace_book(book.id, book_data(member_id=999))

    assert service.get_book(book.id).member_id == 1


def test_replace_book_rejects_another_books_isbn_without_changes(
    service: InMemoryBookService,
) -> None:
    service.create_book(book_data())
    second = service.create_book(book_data(isbn="978-0132350884"))

    with pytest.raises(IsbnAlreadyExistsError):
        service.replace_book(second.id, book_data())

    assert service.get_book(second.id).isbn == "978-0132350884"


def test_replace_book_raises_for_missing_id(service: InMemoryBookService) -> None:
    with pytest.raises(BookNotFoundError):
        service.replace_book(999, book_data())


def test_delete_book_removes_book(service: InMemoryBookService) -> None:
    book = service.create_book(book_data())

    service.delete_book(book.id)

    assert service.list_books() == []


def test_delete_book_raises_for_missing_id(service: InMemoryBookService) -> None:
    with pytest.raises(BookNotFoundError):
        service.delete_book(999)

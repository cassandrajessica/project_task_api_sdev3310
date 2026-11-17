"""Unit tests for the in-memory Member service contract."""

import pytest

from app.exceptions import (
    MemberEmailAlreadyExistsError,
    MemberHasBooksError,
    MemberNotFoundError,
    MembershipIdAlreadyExistsError,
)
from app.models.book import Book
from app.schemas.members import MemberInput
from app.services.in_memory_store import InMemoryStore
from app.services.members import InMemoryMemberService


@pytest.fixture
def store() -> InMemoryStore:
    # The application store starts with one sample Member and Book. Unit tests
    # start empty so every expected ID and collection is explicit.
    return InMemoryStore(members=[], books=[])


@pytest.fixture
def service(store: InMemoryStore) -> InMemoryMemberService:
    return InMemoryMemberService(store)


def member_data(
    email: str = "ada@example.com",
    membership_id: str = "LIB-1",
) -> MemberInput:
    return MemberInput(
        name="Ada Lovelace",
        email=email,
        membership_id=membership_id,
        phone="555-123-4567",
    )


def related_book(member_id: int) -> Book:
    return Book(
        id=1,
        title="The Pragmatic Programmer",
        author="Andrew Hunt",
        isbn="978-0135957059",
        published_year=2019,
        member_id=member_id,
    )


def test_create_list_and_get_member(service: InMemoryMemberService) -> None:
    created = service.create_member(member_data())

    assert created.id == 1
    assert service.list_members() == [created]
    assert service.get_member(created.id) is created


def test_create_member_generates_the_next_id(service: InMemoryMemberService) -> None:
    first = service.create_member(member_data())
    second = service.create_member(member_data("grace@example.com", "LIB-2"))

    assert second.id == first.id + 1


def test_get_member_raises_for_missing_id(service: InMemoryMemberService) -> None:
    with pytest.raises(MemberNotFoundError):
        service.get_member(999)


def test_create_member_rejects_duplicate_email(
    service: InMemoryMemberService,
) -> None:
    service.create_member(member_data())

    with pytest.raises(MemberEmailAlreadyExistsError):
        service.create_member(member_data(membership_id="LIB-2"))

    assert len(service.list_members()) == 1


def test_create_member_rejects_duplicate_membership_id(
    service: InMemoryMemberService,
) -> None:
    service.create_member(member_data())

    with pytest.raises(MembershipIdAlreadyExistsError):
        service.create_member(member_data(email="grace@example.com"))

    assert len(service.list_members()) == 1


def test_replace_member_updates_fields(service: InMemoryMemberService) -> None:
    member = service.create_member(member_data())

    updated = service.replace_member(
        member.id,
        MemberInput(
            name="Ada King",
            email="ada.king@example.com",
            membership_id="LIB-10",
            phone="(555) 987-6543",
        ),
    )

    assert updated is member
    assert updated.name == "Ada King"
    assert updated.email == "ada.king@example.com"
    assert updated.membership_id == "LIB-10"


def test_replace_member_keeps_its_own_unique_values(
    service: InMemoryMemberService,
) -> None:
    member = service.create_member(member_data())

    updated = service.replace_member(member.id, member_data())

    assert updated.email == "ada@example.com"


def test_replace_member_rejects_another_members_email_without_changes(
    service: InMemoryMemberService,
) -> None:
    service.create_member(member_data())
    second = service.create_member(member_data("grace@example.com", "LIB-2"))

    with pytest.raises(MemberEmailAlreadyExistsError):
        service.replace_member(second.id, member_data(membership_id="LIB-2"))

    assert service.get_member(second.id).email == "grace@example.com"


def test_replace_member_raises_for_missing_id(
    service: InMemoryMemberService,
) -> None:
    with pytest.raises(MemberNotFoundError):
        service.replace_member(999, member_data())


def test_list_member_books_requires_existing_member(
    service: InMemoryMemberService,
) -> None:
    with pytest.raises(MemberNotFoundError):
        service.list_member_books(999)


def test_list_member_books_returns_related_books(
    store: InMemoryStore, service: InMemoryMemberService
) -> None:
    member = service.create_member(member_data())
    book = related_book(member.id)
    store.books.append(book)

    assert service.list_member_books(member.id) == [book]


def test_delete_member_rejects_related_books(
    store: InMemoryStore, service: InMemoryMemberService
) -> None:
    member = service.create_member(member_data())
    store.books.append(related_book(member.id))

    with pytest.raises(MemberHasBooksError):
        service.delete_member(member.id)

    assert service.get_member(member.id) is member


def test_delete_member_removes_member_without_books(
    service: InMemoryMemberService,
) -> None:
    member = service.create_member(member_data())

    service.delete_member(member.id)

    assert service.list_members() == []


def test_delete_member_raises_for_missing_id(
    service: InMemoryMemberService,
) -> None:
    with pytest.raises(MemberNotFoundError):
        service.delete_member(999)

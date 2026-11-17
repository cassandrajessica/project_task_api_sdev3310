"""PostgreSQL integration tests for every BookRepository method."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.member import Member
from app.repositories.books import BookRepository
from app.repositories.members import MemberRepository
from app.schemas.books import BookInput
from app.schemas.members import MemberInput


def test_list_all_returns_books_in_id_order(db_session: Session) -> None:
    """list_all persists and returns Books in the repository's declared order."""
    member = create_member(db_session)
    repository = BookRepository(db_session)
    first = create_book(repository, db_session, "978-0000000001", member.id)
    second = create_book(repository, db_session, "978-0000000002", member.id)

    books = repository.list_all()

    assert [book.id for book in books] == [first.id, second.id]


def test_list_by_member_returns_only_that_members_books(db_session: Session) -> None:
    """list_by_member filters Books through the member_id foreign key column."""
    ada = create_member(db_session, "ada@example.com", "LIB-1")
    grace = create_member(db_session, "grace@example.com", "LIB-2")
    repository = BookRepository(db_session)
    ada_book = create_book(repository, db_session, "978-0000000001", ada.id)
    create_book(repository, db_session, "978-0000000002", grace.id)

    books = repository.list_by_member(ada.id)

    assert [book.id for book in books] == [ada_book.id]


def test_get_by_id_and_isbn_return_existing_book_and_none_when_missing(
    db_session: Session,
) -> None:
    """The Book lookups distinguish a persisted Book from absent values."""
    member = create_member(db_session)
    repository = BookRepository(db_session)
    created = create_book(repository, db_session, "978-0135957059", member.id)

    assert repository.get_by_id(created.id).isbn == "978-0135957059"
    assert repository.get_by_isbn("978-0135957059").id == created.id
    assert repository.get_by_id(999) is None
    assert repository.get_by_isbn("000-0000000000") is None


def test_exists_for_member_reflects_related_books(db_session: Session) -> None:
    """exists_for_member supports the blocked-Member-deletion rule."""
    member = create_member(db_session)
    repository = BookRepository(db_session)

    assert repository.exists_for_member(member.id) is False

    create_book(repository, db_session, "978-0135957059", member.id)

    assert repository.exists_for_member(member.id) is True


def test_create_persists_book_and_generates_id(db_session: Session) -> None:
    """create maps request data to a PostgreSQL row with a generated ID."""
    member = create_member(db_session)
    repository = BookRepository(db_session)

    created = repository.create(book_input("978-0135957059", member.id))
    db_session.commit()

    assert created.id > 0
    stored = repository.get_by_id(created.id)
    assert stored is not None
    assert stored.title == "The Pragmatic Programmer"
    assert stored.member_id == member.id


def test_unique_constraint_rejects_duplicate_isbn(db_session: Session) -> None:
    """The database rejects a duplicate ISBN even if the service is bypassed."""
    member = create_member(db_session)
    repository = BookRepository(db_session)
    create_book(repository, db_session, "978-0135957059", member.id)

    with pytest.raises(IntegrityError):
        repository.create(book_input("978-0135957059", member.id))

    db_session.rollback()
    assert len(repository.list_all()) == 1


def test_foreign_key_rejects_book_for_nonexistent_member(
    db_session: Session,
) -> None:
    """The Member-to-Book foreign key rejects an orphan Book row."""
    repository = BookRepository(db_session)

    with pytest.raises(IntegrityError):
        repository.create(book_input("978-0135957059", member_id=999))

    db_session.rollback()
    assert repository.list_all() == []


def test_foreign_key_prevents_deleting_member_with_books(
    db_session: Session,
) -> None:
    """PostgreSQL keeps a Book's Member even if the service check is bypassed."""
    member = create_member(db_session)
    create_book(BookRepository(db_session), db_session, "978-0135957059", member.id)

    MemberRepository(db_session).delete(member)
    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
    assert MemberRepository(db_session).get_by_id(member.id) is not None


def test_replace_updates_persisted_book(db_session: Session) -> None:
    """replace changes every editable Book column, including its Member."""
    ada = create_member(db_session, "ada@example.com", "LIB-1")
    grace = create_member(db_session, "grace@example.com", "LIB-2")
    repository = BookRepository(db_session)
    book = create_book(repository, db_session, "978-0135957059", ada.id)

    updated = repository.replace(
        book,
        BookInput(
            title="Clean Code",
            author="Robert C. Martin",
            isbn="978-0132350884",
            published_year=2008,
            member_id=grace.id,
        ),
    )
    db_session.commit()
    db_session.refresh(updated)

    assert updated.title == "Clean Code"
    assert updated.isbn == "978-0132350884"
    assert updated.published_year == 2008
    assert updated.member_id == grace.id


def test_delete_removes_persisted_book(db_session: Session) -> None:
    """delete removes a Book row after its transaction is committed."""
    member = create_member(db_session)
    repository = BookRepository(db_session)
    book = create_book(repository, db_session, "978-0135957059", member.id)

    repository.delete(book)
    db_session.commit()

    assert repository.get_by_id(book.id) is None


# HELPERS


def book_input(isbn: str, member_id: int) -> BookInput:
    """Return a valid Book request with the given ISBN and Member."""
    return BookInput(
        title="The Pragmatic Programmer",
        author="Andrew Hunt",
        isbn=isbn,
        published_year=2019,
        member_id=member_id,
    )


def create_member(
    session: Session,
    email: str = "ada@example.com",
    membership_id: str = "LIB-1",
) -> Member:
    """Create and commit the parent Member that Books reference."""
    member = MemberRepository(session).create(
        MemberInput(
            name="Ada Lovelace",
            email=email,
            membership_id=membership_id,
            phone="555-123-4567",
        )
    )
    session.commit()
    session.refresh(member)
    return member


def create_book(
    repository: BookRepository,
    session: Session,
    isbn: str,
    member_id: int,
):
    """Create and commit one Book used by a repository test."""
    book = repository.create(book_input(isbn, member_id))
    session.commit()
    session.refresh(book)
    return book

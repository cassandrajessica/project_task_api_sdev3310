"""Unit tests for DatabaseBookService with mocked repositories.

These tests replace the SQLAlchemy session factory and both repositories with
Mockito test doubles. They verify the service's own decisions (which checks run,
which exception is raised, and when a write is skipped) without PostgreSQL.
"""

from collections.abc import Generator
from types import SimpleNamespace

import pytest
from mockito import args, mock, unstub, verify, when
from sqlalchemy.exc import IntegrityError

import app.services.books.database as database_module
from app.exceptions import (
    BookNotFoundError,
    IsbnAlreadyExistsError,
    MemberNotFoundError,
)
from app.models.book import Book
from app.models.member import Member
from app.schemas.books import BookInput
from app.services.books import DatabaseBookService


@pytest.fixture
def session_factory() -> Generator[tuple[object, object, object, object], None, None]:
    """Build fake database collaborators for service unit tests.

    The service uses two session-factory forms:

    * ``session_factory()`` opens a Session for reads.
    * ``session_factory.begin()`` opens a transaction for writes.

    The context-manager stubs are needed because the production service uses
    ``with``. Python enters a context manager by calling ``__enter__`` and
    leaves it by calling ``__exit__``; Mockito must provide those methods so
    the fake factory can yield the fake Session. The last two returned mocks
    are the Book and Member repositories that the test injects into the
    service.
    """
    session = mock()
    factory = mock()
    book_repository = mock()
    member_repository = mock()
    read_context = mock()
    transaction_context = mock()

    # Simulate: ``with session_factory() as session``.
    when(read_context).__enter__().thenReturn(session)
    # `__exit__` receives exception type, value, and traceback; Mockito's
    # `args` matcher accepts any values for those cleanup arguments.
    when(read_context).__exit__(*args)
    when(factory).__call__().thenReturn(read_context)

    # Simulate: ``with session_factory.begin() as session``.
    when(transaction_context).__enter__().thenReturn(session)
    # Match all arguments passed when Python leaves the `with` block.
    when(transaction_context).__exit__(*args)
    when(factory).begin().thenReturn(transaction_context)

    # Route the service's repository constructors to the test doubles.
    when(database_module).BookRepository(session).thenReturn(book_repository)
    when(database_module).MemberRepository(session).thenReturn(member_repository)

    try:
        # Yield the fake collaborators to the test. Pytest pauses this fixture
        # here while the test runs.
        yield factory, session, book_repository, member_repository
    finally:
        # Remove Mockito stubs so they cannot affect a later test.
        unstub()


def test_create_book_verifies_member_and_uses_a_transaction(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, session, book_repository, member_repository = session_factory
    book = stored_book()
    when(member_repository).get_by_id(1).thenReturn(parent_member())
    when(book_repository).get_by_isbn(...).thenReturn(None)
    when(book_repository).create(...).thenReturn(book)

    result = DatabaseBookService(factory).create_book(book_input())

    assert result is book
    verify(member_repository, times=1).get_by_id(1)
    verify(book_repository, times=1).create(...)
    verify(session, times=1).refresh(book)
    verify(factory, times=1).begin()


def test_create_book_rejects_a_missing_member_before_writing(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, _, book_repository, member_repository = session_factory
    when(member_repository).get_by_id(999).thenReturn(None)

    with pytest.raises(MemberNotFoundError):
        DatabaseBookService(factory).create_book(book_input(member_id=999))

    verify(book_repository, times=0).create(...)


def test_create_book_rejects_duplicate_isbn_before_writing(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, _, book_repository, member_repository = session_factory
    when(member_repository).get_by_id(1).thenReturn(parent_member())
    when(book_repository).get_by_isbn(...).thenReturn(stored_book(id=2))

    with pytest.raises(IsbnAlreadyExistsError):
        DatabaseBookService(factory).create_book(book_input())

    verify(book_repository, times=0).create(...)


def test_create_book_translates_a_foreign_key_violation(
    session_factory: tuple[object, object, object, object],
) -> None:
    """A Member deleted concurrently still becomes a 404 outcome, not a 500."""
    factory, _, book_repository, member_repository = session_factory
    when(member_repository).get_by_id(1).thenReturn(parent_member())
    when(book_repository).get_by_isbn(...).thenReturn(None)
    when(book_repository).create(...).thenRaise(
        integrity_error(constraint_name=database_module.BOOK_MEMBER_FOREIGN_KEY)
    )

    with pytest.raises(MemberNotFoundError):
        DatabaseBookService(factory).create_book(book_input())


def test_get_book_translates_missing_repository_result(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, _, book_repository, _ = session_factory
    when(book_repository).get_by_id(999).thenReturn(None)

    with pytest.raises(BookNotFoundError):
        DatabaseBookService(factory).get_book(999)

    # Reads use the plain session factory, not a write transaction.
    verify(factory, times=0).begin()


def test_replace_book_rejects_a_missing_member_without_writing(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, _, book_repository, member_repository = session_factory
    when(book_repository).get_by_id(1).thenReturn(stored_book())
    when(member_repository).get_by_id(999).thenReturn(None)

    with pytest.raises(MemberNotFoundError):
        DatabaseBookService(factory).replace_book(1, book_input(member_id=999))

    verify(book_repository, times=0).replace(...)


def test_delete_book_skips_the_write_for_a_missing_book(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, _, book_repository, _ = session_factory
    when(book_repository).get_by_id(999).thenReturn(None)

    with pytest.raises(BookNotFoundError):
        DatabaseBookService(factory).delete_book(999)

    verify(book_repository, times=0).delete(...)


def test_delete_book_removes_an_existing_book(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, _, book_repository, _ = session_factory
    book = stored_book()
    when(book_repository).get_by_id(1).thenReturn(book)

    DatabaseBookService(factory).delete_book(1)

    verify(book_repository, times=1).delete(book)
    verify(factory, times=1).begin()


# HELPERS


def book_input(member_id: int = 1) -> BookInput:
    """Return a valid Book request for service scenarios."""
    return BookInput(
        title="The Pragmatic Programmer",
        author="Andrew Hunt",
        isbn="978-0135957059",
        published_year=2019,
        member_id=member_id,
    )


def stored_book(id: int = 1) -> Book:
    """Return a Book as a repository would after a database read."""
    return Book(id=id, **book_input().model_dump())


def parent_member() -> Member:
    """Return the Member that a valid Book references."""
    return Member(
        id=1,
        name="Ada Lovelace",
        email="ada@example.com",
        membership_id="LIB-1",
        phone="555-123-4567",
    )


def integrity_error(constraint_name: str) -> IntegrityError:
    """Build an IntegrityError carrying a PostgreSQL constraint name.

    Psycopg exposes the violated constraint on ``error.orig.diag``. A simple
    namespace provides only the attribute the service reads.
    """
    original = SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint_name))
    return IntegrityError("INSERT INTO books ...", {}, original)

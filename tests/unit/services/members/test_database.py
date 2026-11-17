"""Unit tests for DatabaseMemberService with mocked repositories.

These tests replace the SQLAlchemy session factory and both repositories with
Mockito test doubles. They verify the service's own decisions (which checks run,
which exception is raised, and when a write is skipped) without PostgreSQL.
"""

from collections.abc import Generator
from types import SimpleNamespace

import pytest
from mockito import args, mock, unstub, verify, when
from sqlalchemy.exc import IntegrityError

import app.services.members.database as database_module
from app.exceptions import (
    MemberEmailAlreadyExistsError,
    MemberHasBooksError,
    MemberNotFoundError,
)
from app.models.member import Member
from app.schemas.members import MemberInput
from app.services.members import DatabaseMemberService


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
    are the Member and Book repositories that the test injects into the
    service.
    """
    session = mock()
    factory = mock()
    member_repository = mock()
    book_repository = mock()
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

    # Route the service's repository constructors to the test doubles. The
    # service builds repositories inside each operation, so the module-level
    # names are replaced rather than the repository instances.
    when(database_module).MemberRepository(session).thenReturn(member_repository)
    when(database_module).BookRepository(session).thenReturn(book_repository)

    try:
        # Yield the fake collaborators to the test. Pytest pauses this fixture
        # here while the test runs.
        yield factory, session, member_repository, book_repository
    finally:
        # Remove Mockito stubs so they cannot affect a later test.
        unstub()


def test_create_member_checks_uniqueness_and_uses_a_transaction(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, session, member_repository, _ = session_factory
    member = stored_member()
    when(member_repository).get_by_email(...).thenReturn(None)
    when(member_repository).get_by_membership_id(...).thenReturn(None)
    when(member_repository).create(...).thenReturn(member)

    result = DatabaseMemberService(factory).create_member(member_input())

    assert result is member
    verify(member_repository, times=1).get_by_email("ada@example.com")
    verify(member_repository, times=1).get_by_membership_id("LIB-1")
    verify(member_repository, times=1).create(...)
    verify(session, times=1).refresh(member)
    verify(factory, times=1).begin()


def test_create_member_rejects_duplicate_email_before_writing(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, _, member_repository, _ = session_factory
    when(member_repository).get_by_email(...).thenReturn(stored_member(id=2))

    with pytest.raises(MemberEmailAlreadyExistsError):
        DatabaseMemberService(factory).create_member(member_input())

    verify(member_repository, times=0).create(...)


def test_create_member_translates_a_unique_constraint_violation(
    session_factory: tuple[object, object, object, object],
) -> None:
    """A concurrent duplicate that reaches PostgreSQL still becomes a 409 outcome."""
    factory, _, member_repository, _ = session_factory
    when(member_repository).get_by_email(...).thenReturn(None)
    when(member_repository).get_by_membership_id(...).thenReturn(None)
    when(member_repository).create(...).thenRaise(
        integrity_error(constraint_name=database_module.EMAIL_UNIQUE_CONSTRAINT)
    )

    with pytest.raises(MemberEmailAlreadyExistsError):
        DatabaseMemberService(factory).create_member(member_input())


def test_get_member_translates_missing_repository_result(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, _, member_repository, _ = session_factory
    when(member_repository).get_by_id(999).thenReturn(None)

    with pytest.raises(MemberNotFoundError):
        DatabaseMemberService(factory).get_member(999)

    # Reads use the plain session factory, not a write transaction.
    verify(factory, times=0).begin()


def test_replace_member_skips_the_write_for_a_missing_member(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, _, member_repository, _ = session_factory
    when(member_repository).get_by_id(999).thenReturn(None)

    with pytest.raises(MemberNotFoundError):
        DatabaseMemberService(factory).replace_member(999, member_input())

    verify(member_repository, times=0).replace(...)


def test_delete_member_rejects_a_member_with_books(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, _, member_repository, book_repository = session_factory
    member = stored_member()
    when(member_repository).get_by_id(1).thenReturn(member)
    when(book_repository).exists_for_member(1).thenReturn(True)

    with pytest.raises(MemberHasBooksError):
        DatabaseMemberService(factory).delete_member(1)

    verify(member_repository, times=0).delete(...)


def test_delete_member_removes_a_member_without_books(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, _, member_repository, book_repository = session_factory
    member = stored_member()
    when(member_repository).get_by_id(1).thenReturn(member)
    when(book_repository).exists_for_member(1).thenReturn(False)

    DatabaseMemberService(factory).delete_member(1)

    verify(member_repository, times=1).delete(member)
    verify(factory, times=1).begin()


def test_list_member_books_requires_an_existing_member(
    session_factory: tuple[object, object, object, object],
) -> None:
    factory, _, member_repository, book_repository = session_factory
    when(member_repository).get_by_id(999).thenReturn(None)

    with pytest.raises(MemberNotFoundError):
        DatabaseMemberService(factory).list_member_books(999)

    verify(book_repository, times=0).list_by_member(...)


# HELPERS


def member_input() -> MemberInput:
    """Return a valid Member request for service scenarios."""
    return MemberInput(
        name="Ada Lovelace",
        email="ada@example.com",
        membership_id="LIB-1",
        phone="555-123-4567",
    )


def stored_member(id: int = 1) -> Member:
    """Return a Member as a repository would after a database read."""
    return Member(id=id, **member_input().model_dump())


def integrity_error(constraint_name: str) -> IntegrityError:
    """Build an IntegrityError carrying a PostgreSQL constraint name.

    Psycopg exposes the violated constraint on ``error.orig.diag``. A simple
    namespace provides only the attributes the service reads.
    """
    original = SimpleNamespace(
        diag=SimpleNamespace(
            constraint_name=constraint_name,
            table_name=None,
            column_name=None,
        )
    )
    return IntegrityError("INSERT INTO members ...", {}, original)

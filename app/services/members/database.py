"""Relational-database Member service implementation."""

from typing import NoReturn

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.exceptions import (
    MemberEmailAlreadyExistsError,
    MemberHasBooksError,
    MemberNotFoundError,
    MembershipIdAlreadyExistsError,
)
from app.models.book import Book
from app.models.member import Member
from app.repositories.books import BookRepository
from app.repositories.members import MemberRepository
from app.schemas.members import MemberInput
from .base import MemberService

# PostgreSQL's default names for the constraints declared on the ORM models.
EMAIL_UNIQUE_CONSTRAINT = "members_email_key"
MEMBERSHIP_ID_UNIQUE_CONSTRAINT = "members_membership_id_key"
BOOK_MEMBER_FOREIGN_KEY = "books_member_id_fkey"


def _raise_application_error(error: IntegrityError) -> NoReturn:
    """Convert a database constraint violation into an application exception.

    The service checks run first, but two concurrent requests can both pass a
    check before either commits. The database constraint then rejects the
    second write, and this keeps the client response a clean 409 instead of a
    500 that exposes database details.
    """
    diag = getattr(error.orig, "diag", None)
    constraint = getattr(diag, "constraint_name", None)
    if constraint == EMAIL_UNIQUE_CONSTRAINT:
        raise MemberEmailAlreadyExistsError from None
    if constraint == MEMBERSHIP_ID_UNIQUE_CONSTRAINT:
        raise MembershipIdAlreadyExistsError from None
    if constraint == BOOK_MEMBER_FOREIGN_KEY:
        raise MemberHasBooksError from None
    # When a Member is deleted, SQLAlchemy tries to set member_id to NULL on any
    # Books it finds for that Member. NOT NULL rejects that, which also means
    # the Member still has Books.
    if (getattr(diag, "table_name", None), getattr(diag, "column_name", None)) == (
        "books",
        "member_id",
    ):
        raise MemberHasBooksError from None
    raise error


def _ensure_unique(
    repository: MemberRepository,
    data: MemberInput,
    member_id: int | None = None,
) -> None:
    """Reject an email or membership ID used by a different Member.

    member_id lets a replacement keep its own existing values.
    """
    existing = repository.get_by_email(data.email)
    if existing is not None and existing.id != member_id:
        raise MemberEmailAlreadyExistsError
    existing = repository.get_by_membership_id(data.membership_id)
    if existing is not None and existing.id != member_id:
        raise MembershipIdAlreadyExistsError


class DatabaseMemberService(MemberService):
    """Implement Member use cases with database persistence.

    The service applies application rules and defines transaction boundaries.
    """

    def __init__(self, session_factory: sessionmaker[Session]):
        # Share the factory; each operation creates its own Session.
        self._session_factory = session_factory

    def list_members(self) -> list[Member]:
        with self._session_factory() as session:
            return MemberRepository(session).list_all()

    def get_member(self, member_id: int) -> Member:
        with self._session_factory() as session:
            member = MemberRepository(session).get_by_id(member_id)
            if member is None:
                raise MemberNotFoundError
            return member

    def create_member(self, data: MemberInput) -> Member:
        try:
            # begin() commits on success and rolls back if an exception escapes.
            with self._session_factory.begin() as session:
                repository = MemberRepository(session)
                _ensure_unique(repository, data)
                member = repository.create(data)
                session.refresh(member)
                return member
        except IntegrityError as error:
            _raise_application_error(error)

    def replace_member(self, member_id: int, data: MemberInput) -> Member:
        try:
            # Read, validate, update, and commit are one atomic use case.
            with self._session_factory.begin() as session:
                repository = MemberRepository(session)
                member = repository.get_by_id(member_id)
                if member is None:
                    raise MemberNotFoundError
                _ensure_unique(repository, data, member_id)
                updated_member = repository.replace(member, data)
                session.refresh(updated_member)
                return updated_member
        except IntegrityError as error:
            _raise_application_error(error)

    def delete_member(self, member_id: int) -> None:
        try:
            # Check and delete belong to one transaction.
            with self._session_factory.begin() as session:
                repository = MemberRepository(session)
                member = repository.get_by_id(member_id)
                if member is None:
                    raise MemberNotFoundError
                if BookRepository(session).exists_for_member(member_id):
                    raise MemberHasBooksError
                repository.delete(member)
        except IntegrityError as error:
            _raise_application_error(error)

    def list_member_books(self, member_id: int) -> list[Book]:
        with self._session_factory() as session:
            if MemberRepository(session).get_by_id(member_id) is None:
                raise MemberNotFoundError
            return BookRepository(session).list_by_member(member_id)

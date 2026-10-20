"""Relational-database Book service implementation."""

from typing import NoReturn

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.exceptions import (
    BookNotFoundError,
    IsbnAlreadyExistsError,
    MemberNotFoundError,
)
from app.models.book import Book
from app.repositories.books import BookRepository
from app.repositories.members import MemberRepository
from app.schemas.books import BookInput
from .base import BookService

# PostgreSQL's default names for the constraints declared on the Book model.
ISBN_UNIQUE_CONSTRAINT = "books_isbn_key"
BOOK_MEMBER_FOREIGN_KEY = "books_member_id_fkey"


def _raise_application_error(error: IntegrityError) -> NoReturn:
    """Convert a database constraint violation into an application exception.

    The service checks run first, but a concurrent request can change the data
    before this transaction commits (for example, by using the same ISBN or
    deleting the Member). The database constraint then rejects the write, and
    this keeps the client response a clean 404 or 409 instead of a 500.
    """
    constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    if constraint == ISBN_UNIQUE_CONSTRAINT:
        raise IsbnAlreadyExistsError from None
    if constraint == BOOK_MEMBER_FOREIGN_KEY:
        raise MemberNotFoundError from None
    raise error


def _ensure_unique_isbn(
    repository: BookRepository,
    isbn: str,
    book_id: int | None = None,
) -> None:
    """Reject an ISBN used by a different Book.

    book_id lets a replacement keep its own existing ISBN.
    """
    existing = repository.get_by_isbn(isbn)
    if existing is not None and existing.id != book_id:
        raise IsbnAlreadyExistsError


class DatabaseBookService(BookService):
    """Implement Book use cases with database persistence.

    The service applies application rules and defines transaction boundaries.
    """

    def __init__(self, session_factory: sessionmaker[Session]):
        # Share the factory; each operation creates its own Session.
        self._session_factory = session_factory

    def list_books(self) -> list[Book]:
        with self._session_factory() as session:
            return BookRepository(session).list_all()

    def get_book(self, book_id: int) -> Book:
        with self._session_factory() as session:
            book = BookRepository(session).get_by_id(book_id)
            if book is None:
                raise BookNotFoundError
            return book

    def create_book(self, data: BookInput) -> Book:
        try:
            # Verify the parent, check the ISBN, and insert the child atomically.
            with self._session_factory.begin() as session:
                if MemberRepository(session).get_by_id(data.member_id) is None:
                    raise MemberNotFoundError
                repository = BookRepository(session)
                _ensure_unique_isbn(repository, data.isbn)
                book = repository.create(data)
                session.refresh(book)
                return book
        except IntegrityError as error:
            _raise_application_error(error)

    def replace_book(self, book_id: int, data: BookInput) -> Book:
        try:
            # Lookup, validation, update, and commit are one atomic use case.
            with self._session_factory.begin() as session:
                repository = BookRepository(session)
                book = repository.get_by_id(book_id)
                if book is None:
                    raise BookNotFoundError
                if MemberRepository(session).get_by_id(data.member_id) is None:
                    raise MemberNotFoundError
                _ensure_unique_isbn(repository, data.isbn, book_id)
                updated_book = repository.replace(book, data)
                session.refresh(updated_book)
                return updated_book
        except IntegrityError as error:
            _raise_application_error(error)

    def delete_book(self, book_id: int) -> None:
        with self._session_factory.begin() as session:
            repository = BookRepository(session)
            book = repository.get_by_id(book_id)
            if book is None:
                raise BookNotFoundError
            repository.delete(book)

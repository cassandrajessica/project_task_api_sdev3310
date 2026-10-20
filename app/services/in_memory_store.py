"""Shared in-memory state for the alternative service implementations."""

from dataclasses import dataclass, field
from threading import RLock

from app.models.book import Book
from app.models.member import Member


def _sample_members() -> list[Member]:
    return [
        Member(
            id=1,
            name="Ada Lovelace",
            email="ada@example.com",
            membership_id="LIB-1",
            phone="555-123-4567",
        )
    ]


def _sample_books() -> list[Book]:
    return [
        Book(
            id=1,
            title="The Pragmatic Programmer",
            author="Andrew Hunt",
            isbn="978-0135957059",
            published_year=2019,
            member_id=1,
        )
    ]


@dataclass
class InMemoryStore:
    """Hold Members and Books for one application-scoped in-memory service pair.

    The memory backend starts with one sample Member and Book so the endpoints
    return data immediately, as in Assignment 1. The database backend starts
    empty because its data persists between restarts.
    """

    members: list[Member] = field(default_factory=_sample_members)
    books: list[Book] = field(default_factory=_sample_books)
    # One process-local lock protects compound operations such as ID
    # generation, relationship checks, uniqueness checks, and list mutation.
    lock: RLock = field(default_factory=RLock, repr=False)

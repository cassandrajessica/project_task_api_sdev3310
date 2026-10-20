"""SQLAlchemy model for the members table."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Member(Base):
    """Map Member objects to rows in the members table."""

    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # unique=True adds a database-level constraint, so duplicates are rejected
    # even if a request bypasses the service-layer checks.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    membership_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False)

    # The relationship lets Python navigate member.books. The foreign key is
    # stored on Book because Book is the "many" side of the relationship.
    books: Mapped[list[Book]] = relationship(back_populates="member")

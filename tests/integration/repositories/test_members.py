"""PostgreSQL integration tests for every MemberRepository method."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.repositories.members import MemberRepository
from app.schemas.members import MemberInput


def test_list_all_returns_members_in_id_order(db_session: Session) -> None:
    """list_all persists and returns Members in the repository's declared order."""
    repository = MemberRepository(db_session)
    first = create_member(repository, db_session, "first@example.com", "LIB-1")
    second = create_member(repository, db_session, "second@example.com", "LIB-2")

    members = repository.list_all()

    assert [member.id for member in members] == [first.id, second.id]


def test_get_by_id_returns_existing_member_and_none_when_missing(
    db_session: Session,
) -> None:
    """get_by_id distinguishes a persisted Member from an absent ID."""
    repository = MemberRepository(db_session)
    created = create_member(repository, db_session, "ada@example.com", "LIB-1")

    found = repository.get_by_id(created.id)

    assert found is not None
    assert found.id == created.id
    assert found.email == "ada@example.com"
    assert repository.get_by_id(999) is None


def test_get_by_email_and_membership_id_find_stored_values(
    db_session: Session,
) -> None:
    """The uniqueness lookups used by the service query PostgreSQL correctly."""
    repository = MemberRepository(db_session)
    created = create_member(repository, db_session, "ada@example.com", "LIB-1")

    assert repository.get_by_email("ada@example.com").id == created.id
    assert repository.get_by_membership_id("LIB-1").id == created.id
    assert repository.get_by_email("missing@example.com") is None
    assert repository.get_by_membership_id("LIB-999") is None


def test_create_persists_member_and_generates_id(db_session: Session) -> None:
    """create maps request data to a PostgreSQL row with a generated ID."""
    repository = MemberRepository(db_session)

    created = repository.create(member_input("ada@example.com", "LIB-1"))
    db_session.commit()

    assert created.id > 0
    stored = repository.get_by_id(created.id)
    assert stored is not None
    assert stored.name == "Ada Lovelace"
    assert stored.membership_id == "LIB-1"
    assert stored.phone == "555-123-4567"


def test_generated_ids_increase_for_each_new_member(db_session: Session) -> None:
    """PostgreSQL assigns a new, larger identifier to every inserted Member."""
    repository = MemberRepository(db_session)
    first = create_member(repository, db_session, "first@example.com", "LIB-1")
    second = create_member(repository, db_session, "second@example.com", "LIB-2")

    assert second.id > first.id


@pytest.mark.parametrize(
    ("email", "membership_id"),
    [("ada@example.com", "LIB-2"), ("grace@example.com", "LIB-1")],
    ids=["duplicate-email", "duplicate-membership-id"],
)
def test_unique_constraints_reject_duplicate_member_values(
    db_session: Session,
    email: str,
    membership_id: str,
) -> None:
    """The database rejects duplicates even if the service checks are bypassed."""
    repository = MemberRepository(db_session)
    create_member(repository, db_session, "ada@example.com", "LIB-1")

    with pytest.raises(IntegrityError):
        repository.create(member_input(email, membership_id))

    db_session.rollback()
    assert len(repository.list_all()) == 1


def test_replace_updates_persisted_member(db_session: Session) -> None:
    """replace changes every editable Member column in PostgreSQL."""
    repository = MemberRepository(db_session)
    member = create_member(repository, db_session, "ada@example.com", "LIB-1")

    updated = repository.replace(
        member,
        MemberInput(
            name="Ada King",
            email="ada.king@example.com",
            membership_id="LIB-10",
            phone="(555) 987-6543",
        ),
    )
    db_session.commit()
    db_session.refresh(updated)

    assert updated.name == "Ada King"
    assert updated.email == "ada.king@example.com"
    assert updated.membership_id == "LIB-10"
    assert updated.phone == "(555) 987-6543"


def test_delete_removes_persisted_member(db_session: Session) -> None:
    """delete removes a Member row after its transaction is committed."""
    repository = MemberRepository(db_session)
    member = create_member(repository, db_session, "ada@example.com", "LIB-1")

    repository.delete(member)
    db_session.commit()

    assert repository.get_by_id(member.id) is None


# HELPERS


def member_input(email: str, membership_id: str) -> MemberInput:
    """Return a valid Member request with the given unique values."""
    return MemberInput(
        name="Ada Lovelace",
        email=email,
        membership_id=membership_id,
        phone="555-123-4567",
    )


def create_member(
    repository: MemberRepository,
    session: Session,
    email: str,
    membership_id: str,
):
    """Create and commit one Member used by a repository test."""
    member = repository.create(member_input(email, membership_id))
    session.commit()
    session.refresh(member)
    return member

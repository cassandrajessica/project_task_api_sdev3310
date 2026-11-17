"""Unit tests for every Member Pydantic schema and declared rule."""

import pytest
from pydantic import ValidationError

from app.models.member import Member
from app.schemas.members import MemberInput, MemberResponse


@pytest.mark.parametrize("missing_field", ["name", "email", "membership_id", "phone"])
def test_member_create_requires_each_declared_field(missing_field: str) -> None:
    """A create request must include every Member field."""
    data = valid_member_data()
    data.pop(missing_field)

    with pytest.raises(ValidationError):
        MemberInput(**data)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("name", "   "),
        ("name", "n" * 121),
        ("membership_id", "   "),
        ("membership_id", "L" * 51),
    ],
    ids=[
        "blank-name",
        "name-over-maximum",
        "blank-membership-id",
        "membership-id-over-maximum",
    ],
)
def test_member_create_enforces_field_boundaries(
    field_name: str,
    value: str,
) -> None:
    """Member text fields must satisfy their declared length constraints."""
    data = valid_member_data()
    data[field_name] = value

    with pytest.raises(ValidationError):
        MemberInput(**data)


def test_member_create_accepts_declared_maximum_lengths() -> None:
    """The inclusive maximum lengths remain valid request values."""
    data = valid_member_data()
    data["name"] = "n" * 120
    data["membership_id"] = "L" * 50

    member = MemberInput(**data)

    assert len(member.name) == 120
    assert len(member.membership_id) == 50


@pytest.mark.parametrize(
    "email",
    ["not-an-email", "ada@", "@example.com", "ada example.com"],
)
def test_member_create_rejects_invalid_email(email: str) -> None:
    """EmailStr rejects values that are not valid email addresses."""
    data = valid_member_data()
    data["email"] = email

    with pytest.raises(ValidationError):
        MemberInput(**data)


@pytest.mark.parametrize(
    "phone",
    ["555-123-4567", "(555) 123-4567", "555.123.4567", "555 123 4567", "5551234567"],
)
def test_member_create_accepts_documented_phone_formats(phone: str) -> None:
    """The phone pattern accepts each US format documented in the README."""
    data = valid_member_data()
    data["phone"] = phone

    assert MemberInput(**data).phone == phone


@pytest.mark.parametrize(
    "phone",
    ["555-1234", "555-123-45678", "phone-number", "+1 555 123 4567", ""],
    ids=["too-short", "too-long", "letters", "country-code", "empty"],
)
def test_member_create_rejects_invalid_phone(phone: str) -> None:
    """The phone pattern rejects values outside the US format."""
    data = valid_member_data()
    data["phone"] = phone

    with pytest.raises(ValidationError):
        MemberInput(**data)


def test_member_create_strips_surrounding_whitespace() -> None:
    """Shared schema configuration normalizes string input before validation."""
    member = MemberInput(
        name="  Ada Lovelace  ",
        email="  ada@example.com  ",
        membership_id="  LIB-1  ",
        phone="  555-123-4567  ",
    )

    assert member.name == "Ada Lovelace"
    assert member.email == "ada@example.com"
    assert member.membership_id == "LIB-1"
    assert member.phone == "555-123-4567"


def test_member_create_rejects_undocumented_field() -> None:
    """The request contract rejects input outside the documented schema."""
    with pytest.raises(ValidationError):
        MemberInput(**valid_member_data(), address="12 Library Lane")


def test_member_response_reads_an_orm_member() -> None:
    """The response schema serializes attributes from an ORM model instance."""
    source = Member(id=1, **valid_member_data())

    response = MemberResponse.model_validate(source)

    assert response.model_dump() == {**valid_member_data(), "id": 1}


def test_member_response_rejects_nonpositive_server_id() -> None:
    """A response must contain a positive server-generated identifier."""
    with pytest.raises(ValidationError):
        MemberResponse(**valid_member_data(), id=0)


# HELPERS


def valid_member_data() -> dict[str, str]:
    """Return a valid Member request body for focused validation scenarios."""
    return {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "membership_id": "LIB-1",
        "phone": "555-123-4567",
    }

"""Negative API tests for invalid, missing, and disallowed client requests.

Every protected write supplies a valid administrator token so these tests
reach validation and business rules instead of stopping at authorization.
Rejected writes are followed by a read that confirms stored data is unchanged.
"""

from typing import Any

import pytest
from starlette.testclient import TestClient

from app.schemas.books import CURRENT_YEAR


# REQUEST-BODY VALIDATION
# FastAPI passes JSON bodies to Pydantic before the route handler completes.
# These tests verify required fields, unknown fields, and field boundaries.


def test_create_member_rejects_missing_required_field(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """A Member request without membership_id is rejected with 422."""
    body = valid_member_body()
    body.pop("membership_id")

    response = database_client.post("/members", json=body, headers=admin_headers)

    assert_validation_error(response, "membership_id", "missing")


def test_create_book_rejects_missing_required_field(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """A Book request without published_year is rejected with 422."""
    body = valid_book_body(member_id=1)
    body.pop("published_year")

    response = database_client.post("/books", json=body, headers=admin_headers)

    assert_validation_error(response, "published_year", "missing")


def test_create_member_rejects_undocumented_field(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """extra='forbid' prevents a client from sending an unknown Member field."""
    response = database_client.post(
        "/members",
        json={**valid_member_body(), "address": "12 Library Lane"},
        headers=admin_headers,
    )

    assert_validation_error(response, "address", "extra_forbidden")


def test_create_book_rejects_undocumented_field(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """extra='forbid' prevents a client from sending an unknown Book field."""
    response = database_client.post(
        "/books",
        json={**valid_book_body(member_id=1), "genre": "Software"},
        headers=admin_headers,
    )

    assert_validation_error(response, "genre", "extra_forbidden")


# REQUEST-BODY BOUNDARY VALIDATION
# These values have the expected JSON fields but violate Pydantic constraints.


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("name", "   "),
        ("name", "n" * 121),
        ("email", "not-an-email"),
        ("phone", "555-1234"),
        ("membership_id", "L" * 51),
    ],
    ids=[
        "blank-name",
        "name-over-maximum",
        "invalid-email",
        "invalid-phone",
        "membership-id-over-maximum",
    ],
)
def test_create_member_rejects_invalid_boundary_values(
    database_client: TestClient,
    admin_headers: dict[str, str],
    field_name: str,
    value: str,
) -> None:
    """Pydantic enforces documented Member boundaries over HTTP."""
    body = valid_member_body()
    body[field_name] = value

    response = database_client.post("/members", json=body, headers=admin_headers)

    assert_validation_error(response, field_name)
    assert database_client.get("/members", headers=admin_headers).json() == []


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("title", "   "),
        ("isbn", "9" * 21),
        ("published_year", 1449),
        ("published_year", CURRENT_YEAR + 1),
        ("member_id", 0),
    ],
    ids=[
        "blank-title",
        "isbn-over-maximum",
        "year-too-early",
        "year-in-future",
        "nonpositive-member-id",
    ],
)
def test_create_book_rejects_invalid_boundary_values(
    database_client: TestClient,
    admin_headers: dict[str, str],
    field_name: str,
    value: Any,
) -> None:
    """Pydantic enforces documented Book boundaries over HTTP."""
    member = create_member(database_client, admin_headers)
    body = valid_book_body(member["id"])
    body[field_name] = value

    response = database_client.post("/books", json=body, headers=admin_headers)

    assert_validation_error(response, field_name)
    assert database_client.get("/books", headers=admin_headers).json() == []


# PATH-PARAMETER VALIDATION
# FastAPI validates the typed `int` path parameters before it calls a route.


@pytest.mark.parametrize(
    "path",
    ["/members/not-an-integer", "/members/LIB-1/books", "/books/not-an-integer"],
    ids=["member-id", "member-books-id", "book-id"],
)
def test_typed_path_parameters_reject_wrong_data_type(
    database_client: TestClient,
    admin_headers: dict[str, str],
    path: str,
) -> None:
    """FastAPI rejects a non-integer resource identifier before the route runs."""
    response = database_client.get(path, headers=admin_headers)

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"][0] == "path"
    assert error["type"] == "int_parsing"


# RESOURCE AND BUSINESS-RULE REJECTIONS
# These requests have a valid shape, so the application layers decide whether
# the requested resource or relationship is allowed and return 404 or 409.


@pytest.mark.parametrize(
    ("method", "path", "detail"),
    [
        ("GET", "/members/999999", "Member not found"),
        ("GET", "/members/999999/books", "Member not found"),
        ("DELETE", "/members/999999", "Member not found"),
        ("GET", "/books/999999", "Book not found"),
        ("DELETE", "/books/999999", "Book not found"),
    ],
)
def test_missing_resources_return_not_found(
    database_client: TestClient,
    admin_headers: dict[str, str],
    method: str,
    path: str,
    detail: str,
) -> None:
    """A valid identifier with no matching resource returns the documented 404."""
    response = database_client.request(method, path, headers=admin_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": detail}


def test_replace_missing_resources_return_not_found(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """PUT to a missing Member or Book returns 404 without creating it."""
    member = create_member(database_client, admin_headers)

    member_response = database_client.put(
        "/members/999999",
        json=valid_member_body("other@example.com", "LIB-2"),
        headers=admin_headers,
    )
    book_response = database_client.put(
        "/books/999999",
        json=valid_book_body(member["id"]),
        headers=admin_headers,
    )

    assert member_response.status_code == 404
    assert book_response.status_code == 404
    assert database_client.get("/members", headers=admin_headers).json() == [member]
    assert database_client.get("/books", headers=admin_headers).json() == []


def test_create_book_rejects_nonexistent_member(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """The Book relationship rule becomes a client-visible 404 response."""
    response = database_client.post(
        "/books",
        json=valid_book_body(member_id=999999),
        headers=admin_headers,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Member not found"}
    assert database_client.get("/books", headers=admin_headers).json() == []


def test_replace_book_rejects_nonexistent_member_without_changes(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """Moving a Book to a missing Member fails and leaves the Book unchanged."""
    member = create_member(database_client, admin_headers)
    book = create_book(database_client, admin_headers, member["id"])

    response = database_client.put(
        f"/books/{book['id']}",
        json=valid_book_body(member_id=999999),
        headers=admin_headers,
    )

    assert response.status_code == 404
    assert (
        database_client.get(f"/books/{book['id']}", headers=admin_headers).json()
        == book
    )


@pytest.mark.parametrize(
    ("email", "membership_id", "detail"),
    [
        ("ada@example.com", "LIB-2", "A member with this email already exists"),
        (
            "grace@example.com",
            "LIB-1",
            "A member with this membership ID already exists",
        ),
    ],
    ids=["duplicate-email", "duplicate-membership-id"],
)
def test_create_member_rejects_duplicate_unique_values(
    database_client: TestClient,
    admin_headers: dict[str, str],
    email: str,
    membership_id: str,
    detail: str,
) -> None:
    """Duplicate Member values return 409 and do not add a second Member."""
    member = create_member(database_client, admin_headers)

    response = database_client.post(
        "/members",
        json=valid_member_body(email, membership_id),
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": detail}
    assert database_client.get("/members", headers=admin_headers).json() == [member]


def test_replace_member_rejects_another_members_email_without_changes(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """A replacement cannot take a value owned by a different Member."""
    create_member(database_client, admin_headers)
    second = create_member(database_client, admin_headers, "grace@example.com", "LIB-2")

    response = database_client.put(
        f"/members/{second['id']}",
        json=valid_member_body("ada@example.com", "LIB-2"),
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert (
        database_client.get(f"/members/{second['id']}", headers=admin_headers).json()
        == second
    )


def test_create_book_rejects_duplicate_isbn(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """A duplicate ISBN returns 409 and does not add a second Book."""
    member = create_member(database_client, admin_headers)
    book = create_book(database_client, admin_headers, member["id"])

    response = database_client.post(
        "/books",
        json=valid_book_body(member["id"]),
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "A book with this ISBN already exists"}
    assert database_client.get("/books", headers=admin_headers).json() == [book]


def test_delete_member_rejects_member_with_related_books(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """A Member with Books remains protected by the documented 409 conflict."""
    member = create_member(database_client, admin_headers)
    book = create_book(database_client, admin_headers, member["id"])

    response = database_client.delete(f"/members/{member['id']}", headers=admin_headers)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Delete the member's books before deleting the member"
    }
    # Neither the Member nor its Book was removed by the rejected request.
    assert (
        database_client.get(f"/members/{member['id']}", headers=admin_headers).json()
        == member
    )
    assert database_client.get(
        f"/members/{member['id']}/books", headers=admin_headers
    ).json() == [book]


# HELPERS


def assert_validation_error(
    response,
    field_name: str,
    error_type: str | None = None,
) -> None:
    """Check FastAPI's 422 status and that the error names the failing field."""
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail
    # FastAPI reports each problem with a location such as ["body", "email"].
    matching = [error for error in detail if error["loc"][-1] == field_name]
    assert matching, f"No validation error reported for {field_name!r}: {detail}"
    if error_type is not None:
        assert matching[0]["type"] == error_type


def valid_member_body(
    email: str = "ada@example.com",
    membership_id: str = "LIB-1",
) -> dict[str, Any]:
    """Return a valid Member request body."""
    return {
        "name": "Ada Lovelace",
        "email": email,
        "membership_id": membership_id,
        "phone": "555-123-4567",
    }


def valid_book_body(member_id: int) -> dict[str, Any]:
    """Return a valid Book request body for the given Member."""
    return {
        "title": "The Pragmatic Programmer",
        "author": "Andrew Hunt",
        "isbn": "978-0135957059",
        "published_year": 2019,
        "member_id": member_id,
    }


def create_member(
    database_client: TestClient,
    admin_headers: dict[str, str],
    email: str = "ada@example.com",
    membership_id: str = "LIB-1",
) -> dict[str, Any]:
    """Create a Member needed by a negative scenario."""
    response = database_client.post(
        "/members",
        json=valid_member_body(email, membership_id),
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


def create_book(
    database_client: TestClient,
    admin_headers: dict[str, str],
    member_id: int,
) -> dict[str, Any]:
    """Create a related Book needed by a negative scenario."""
    response = database_client.post(
        "/books",
        json=valid_book_body(member_id),
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()

"""Integration tests for authentication and role-based authorization."""

import pytest
from starlette.testclient import TestClient

# Valid request bodies let these tests prove that authorization, not request
# validation, is what rejects a member's write.
MEMBER_BODY = {
    "name": "Denied Member",
    "email": "denied@example.com",
    "membership_id": "LIB-DENIED",
    "phone": "555-000-0000",
}
BOOK_BODY = {
    "title": "Denied Book",
    "author": "Denied Author",
    "isbn": "000-DENIED",
    "published_year": 2020,
    "member_id": 1,
}


# PUBLIC AND AUTHENTICATED READS
# Root, health, and API documentation remain public. Resource reads require a
# valid token, and both classroom roles may perform them.


@pytest.mark.parametrize("path", ["/", "/health", "/docs", "/redoc", "/openapi.json"])
def test_root_health_and_documentation_remain_public(
    database_client: TestClient,
    path: str,
) -> None:
    """The introductory and documentation endpoints do not require a token."""
    assert database_client.get(path).status_code == 200


@pytest.mark.parametrize(
    "path",
    ["/members", "/members/1", "/members/1/books", "/books", "/books/1"],
)
def test_protected_reads_reject_a_missing_token(
    database_client: TestClient,
    path: str,
) -> None:
    """A missing Bearer token receives 401 and the standard challenge header."""
    response = database_client.get(path)

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing or invalid Bearer token"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer not-a-classroom-token",
        "Basic YWRtaW46YWRtaW4=",
        "admin-demo-token",
        "Bearer",
    ],
    ids=["unknown-token", "wrong-scheme", "missing-scheme", "missing-token"],
)
def test_protected_read_rejects_unknown_or_malformed_tokens(
    database_client: TestClient,
    authorization: str,
) -> None:
    """Unrecognized or malformed credentials are not treated as a user."""
    response = database_client.get(
        "/books",
        headers={"Authorization": authorization},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("path", ["/members", "/books"])
@pytest.mark.parametrize("headers_fixture", ["member_headers", "admin_headers"])
def test_both_roles_can_read_protected_collections(
    database_client: TestClient,
    request: pytest.FixtureRequest,
    headers_fixture: str,
    path: str,
) -> None:
    """Member and administrator tokens both permit safe resource reads."""
    headers = request.getfixturevalue(headers_fixture)

    response = database_client.get(path, headers=headers)

    assert response.status_code == 200
    assert response.json() == []


# ADMINISTRATOR-ONLY WRITES
# A member is authenticated but lacks the administrator role, so write routes
# return 403 before the service layer can change Library data.


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("POST", "/members", MEMBER_BODY),
        ("PUT", "/members/{member_id}", MEMBER_BODY),
        ("DELETE", "/members/{member_id}", None),
        ("POST", "/books", BOOK_BODY),
        ("PUT", "/books/{book_id}", BOOK_BODY),
        ("DELETE", "/books/{book_id}", None),
    ],
)
def test_member_cannot_use_administrator_only_write_routes(
    database_client: TestClient,
    admin_headers: dict[str, str],
    member_headers: dict[str, str],
    method: str,
    path: str,
    json_body: dict[str, object] | None,
) -> None:
    """Every Member and Book write requires the admin role and changes nothing."""
    member, book = create_library_data(database_client, admin_headers)
    before = library_snapshot(database_client, admin_headers)

    response = database_client.request(
        method,
        path.format(member_id=member["id"], book_id=book["id"]),
        json=json_body,
        headers=member_headers,
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Administrator role required"}
    assert library_snapshot(database_client, admin_headers) == before


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("POST", "/members", MEMBER_BODY),
        ("DELETE", "/members/{member_id}", None),
        ("POST", "/books", BOOK_BODY),
        ("DELETE", "/books/{book_id}", None),
    ],
)
def test_unauthenticated_writes_return_401_and_change_nothing(
    database_client: TestClient,
    admin_headers: dict[str, str],
    method: str,
    path: str,
    json_body: dict[str, object] | None,
) -> None:
    """A write without credentials is rejected before it reaches a service."""
    member, book = create_library_data(database_client, admin_headers)
    before = library_snapshot(database_client, admin_headers)

    response = database_client.request(
        method,
        path.format(member_id=member["id"], book_id=book["id"]),
        json=json_body,
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert library_snapshot(database_client, admin_headers) == before


def test_administrator_can_complete_a_member_and_book_write_workflow(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """An admin token reaches the existing CRUD workflow after authorization."""
    member, book = create_library_data(database_client, admin_headers)

    replace_response = database_client.put(
        f"/books/{book['id']}",
        json={**BOOK_BODY, "isbn": "978-0132350884", "member_id": member["id"]},
        headers=admin_headers,
    )
    assert replace_response.status_code == 200
    assert replace_response.json()["isbn"] == "978-0132350884"

    assert (
        database_client.delete(
            f"/books/{book['id']}", headers=admin_headers
        ).status_code
        == 204
    )
    assert (
        database_client.delete(
            f"/members/{member['id']}", headers=admin_headers
        ).status_code
        == 204
    )


def test_memory_backend_applies_the_same_role_checks(
    memory_client: TestClient,
    member_headers: dict[str, str],
) -> None:
    """Authorization lives at the HTTP boundary, so both backends share it."""
    assert memory_client.get("/books", headers=member_headers).status_code == 200
    assert memory_client.delete("/books/1", headers=member_headers).status_code == 403
    assert memory_client.get("/books/1", headers=member_headers).status_code == 200


# HELPERS


def create_library_data(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> tuple[dict, dict]:
    """Create one Member and one related Book as an administrator."""
    member_response = database_client.post(
        "/members",
        json={
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "membership_id": "LIB-1",
            "phone": "555-123-4567",
        },
        headers=admin_headers,
    )
    assert member_response.status_code == 201
    member = member_response.json()

    book_response = database_client.post(
        "/books",
        json={
            "title": "The Pragmatic Programmer",
            "author": "Andrew Hunt",
            "isbn": "978-0135957059",
            "published_year": 2019,
            "member_id": member["id"],
        },
        headers=admin_headers,
    )
    assert book_response.status_code == 201
    return member, book_response.json()


def library_snapshot(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> tuple[list, list]:
    """Return every stored Member and Book so a test can compare before/after."""
    members = database_client.get("/members", headers=admin_headers).json()
    books = database_client.get("/books", headers=admin_headers).json()
    return members, books

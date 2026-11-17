"""Successful-path integration tests for every Member API endpoint."""

from starlette.testclient import TestClient


def test_create_list_and_get_members(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """POST, GET collection, and GET item work together for Members."""
    first_member = create_member(
        database_client, admin_headers, "ada@example.com", "LIB-1"
    )
    second_member = create_member(
        database_client, admin_headers, "grace@example.com", "LIB-2"
    )

    list_response = database_client.get("/members", headers=admin_headers)

    assert list_response.status_code == 200
    assert list_response.json() == [first_member, second_member]

    get_response = database_client.get(
        f"/members/{first_member['id']}", headers=admin_headers
    )

    assert get_response.status_code == 200
    assert get_response.json() == first_member


def test_create_member_returns_normalized_values(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """The stored Member reflects Pydantic's whitespace trimming."""
    response = database_client.post(
        "/members",
        json={
            "name": "  Ada Lovelace  ",
            "email": "ada@example.com",
            "membership_id": "  LIB-1  ",
            "phone": "555-123-4567",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Ada Lovelace"
    assert response.json()["membership_id"] == "LIB-1"


def test_replace_member_updates_the_public_resource(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """PUT replaces a Member and later GET returns the new values."""
    member = create_member(database_client, admin_headers, "ada@example.com", "LIB-1")

    replace_response = database_client.put(
        f"/members/{member['id']}",
        json={
            "name": "Ada King",
            "email": "ada.king@example.com",
            "membership_id": "LIB-10",
            "phone": "(555) 987-6543",
        },
        headers=admin_headers,
    )

    assert replace_response.status_code == 200
    updated_member = replace_response.json()
    assert updated_member == {
        "id": member["id"],
        "name": "Ada King",
        "email": "ada.king@example.com",
        "membership_id": "LIB-10",
        "phone": "(555) 987-6543",
    }

    get_response = database_client.get(
        f"/members/{member['id']}", headers=admin_headers
    )
    assert get_response.status_code == 200
    assert get_response.json() == updated_member


def test_delete_member_removes_the_public_resource(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """DELETE returns no content and removes a Member from its collection."""
    member = create_member(database_client, admin_headers, "ada@example.com", "LIB-1")

    delete_response = database_client.delete(
        f"/members/{member['id']}", headers=admin_headers
    )

    assert delete_response.status_code == 204
    assert delete_response.content == b""

    list_response = database_client.get("/members", headers=admin_headers)
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_list_member_books_returns_related_books(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """The related-resource endpoint returns Books for the requested Member."""
    member = create_member(database_client, admin_headers, "ada@example.com", "LIB-1")
    other_member = create_member(
        database_client, admin_headers, "grace@example.com", "LIB-2"
    )

    first_book = create_book(
        database_client, admin_headers, "978-0000000001", member["id"]
    )
    second_book = create_book(
        database_client, admin_headers, "978-0000000002", member["id"]
    )
    # A Book for a different Member must not appear in the related list.
    create_book(database_client, admin_headers, "978-0000000003", other_member["id"])

    response = database_client.get(
        f"/members/{member['id']}/books", headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json() == [first_book, second_book]


def test_member_persists_across_application_restarts(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """Database-backed data survives when the FastAPI lifespan starts again."""
    from app.main import app

    member = create_member(database_client, admin_headers, "ada@example.com", "LIB-1")

    # A second TestClient runs the lifespan again, which creates new services
    # and a new engine. Only PostgreSQL connects the two application starts.
    with TestClient(app) as restarted_client:
        response = restarted_client.get(
            f"/members/{member['id']}", headers=admin_headers
        )

    assert response.status_code == 200
    assert response.json() == member


# HELPERS


def create_member(
    database_client: TestClient,
    admin_headers: dict[str, str],
    email: str,
    membership_id: str,
) -> dict:
    """Create one Member through the public API and return its response body."""
    response = database_client.post(
        "/members",
        json={
            "name": "Ada Lovelace",
            "email": email,
            "membership_id": membership_id,
            "phone": "555-123-4567",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


def create_book(
    database_client: TestClient,
    admin_headers: dict[str, str],
    isbn: str,
    member_id: int,
) -> dict:
    """Create one Book through the public API and return its response body."""
    response = database_client.post(
        "/books",
        json={
            "title": "The Pragmatic Programmer",
            "author": "Andrew Hunt",
            "isbn": isbn,
            "published_year": 2019,
            "member_id": member_id,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()

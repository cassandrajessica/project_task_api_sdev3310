"""Successful-path integration tests for every Book API endpoint."""

from starlette.testclient import TestClient


def test_create_list_and_get_books(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """POST, GET collection, and GET item work together for Books."""
    member = create_member(database_client, admin_headers)
    first_book = create_book(
        database_client, admin_headers, "978-0000000001", member["id"]
    )
    second_book = create_book(
        database_client, admin_headers, "978-0000000002", member["id"]
    )

    list_response = database_client.get("/books", headers=admin_headers)

    assert list_response.status_code == 200
    assert list_response.json() == [first_book, second_book]

    get_response = database_client.get(
        f"/books/{first_book['id']}", headers=admin_headers
    )

    assert get_response.status_code == 200
    assert get_response.json() == first_book


def test_replace_book_updates_the_public_resource(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """PUT replaces a Book, including moving it to another Member."""
    ada = create_member(database_client, admin_headers, "ada@example.com", "LIB-1")
    grace = create_member(database_client, admin_headers, "grace@example.com", "LIB-2")
    book = create_book(database_client, admin_headers, "978-0135957059", ada["id"])

    replace_response = database_client.put(
        f"/books/{book['id']}",
        json={
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "isbn": "978-0132350884",
            "published_year": 2008,
            "member_id": grace["id"],
        },
        headers=admin_headers,
    )

    assert replace_response.status_code == 200
    updated_book = replace_response.json()
    assert updated_book == {
        "id": book["id"],
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "isbn": "978-0132350884",
        "published_year": 2008,
        "member_id": grace["id"],
    }

    get_response = database_client.get(f"/books/{book['id']}", headers=admin_headers)
    assert get_response.status_code == 200
    assert get_response.json() == updated_book

    # The relationship moved, so each Member's related list reflects it.
    assert (
        database_client.get(f"/members/{ada['id']}/books", headers=admin_headers).json()
        == []
    )
    assert database_client.get(
        f"/members/{grace['id']}/books", headers=admin_headers
    ).json() == [updated_book]


def test_delete_book_removes_the_public_resource(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """DELETE returns no content and removes a Book from its collection."""
    member = create_member(database_client, admin_headers)
    book = create_book(database_client, admin_headers, "978-0135957059", member["id"])

    delete_response = database_client.delete(
        f"/books/{book['id']}", headers=admin_headers
    )

    assert delete_response.status_code == 204
    assert delete_response.content == b""

    list_response = database_client.get("/books", headers=admin_headers)
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_member_can_be_deleted_after_its_books_are_deleted(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """Removing every related Book clears the blocked-deletion rule."""
    member = create_member(database_client, admin_headers)
    book = create_book(database_client, admin_headers, "978-0135957059", member["id"])

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


# HELPERS


def create_member(
    database_client: TestClient,
    admin_headers: dict[str, str],
    email: str = "ada@example.com",
    membership_id: str = "LIB-1",
) -> dict:
    """Create the parent Member that every Book requires."""
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

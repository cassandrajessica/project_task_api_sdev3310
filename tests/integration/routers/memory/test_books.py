"""In-memory router integration tests for the Book resource.

Every memory-backed application start creates a fresh InMemoryStore that
contains one sample Member (id 1) and one sample Book (id 1). The new Books
below reference the sample Member and use different ISBNs.
"""

from starlette.testclient import TestClient


def test_book_crud_works_with_memory_client(
    memory_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """The Book router works when DI selects the in-memory service."""
    create_response = memory_client.post(
        "/books",
        json=book_body("978-0132350884"),
        headers=admin_headers,
    )

    assert create_response.status_code == 201
    book = create_response.json()
    assert book["id"] == 2

    get_response = memory_client.get(f"/books/{book['id']}", headers=admin_headers)
    assert get_response.status_code == 200
    assert get_response.json() == book

    replace_body = book_body("978-0132350884")
    replace_body["title"] = "Clean Code, Updated"
    replace_response = memory_client.put(
        f"/books/{book['id']}",
        json=replace_body,
        headers=admin_headers,
    )
    assert replace_response.status_code == 200
    assert replace_response.json()["title"] == "Clean Code, Updated"

    delete_response = memory_client.delete(
        f"/books/{book['id']}", headers=admin_headers
    )
    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert [
        item["id"] for item in memory_client.get("/books", headers=admin_headers).json()
    ] == [1]


def test_memory_backend_rejects_duplicate_isbn(
    memory_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """The in-memory service enforces the same ISBN rule as PostgreSQL."""
    response = memory_client.post(
        "/books",
        json=book_body("978-0135957059"),
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert len(memory_client.get("/books", headers=admin_headers).json()) == 1


def test_memory_backend_rejects_book_for_missing_member(
    memory_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """The in-memory service enforces the Member relationship rule."""
    body = book_body("978-0132350884")
    body["member_id"] = 999

    response = memory_client.post("/books", json=body, headers=admin_headers)

    assert response.status_code == 404
    assert len(memory_client.get("/books", headers=admin_headers).json()) == 1


# HELPERS


def book_body(isbn: str) -> dict:
    """Return a valid Book request body that references the sample Member."""
    return {
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "isbn": isbn,
        "published_year": 2008,
        "member_id": 1,
    }

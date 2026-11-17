"""In-memory router integration tests for the Member resource.

Every memory-backed application start creates a fresh InMemoryStore that
contains one sample Member (id 1, LIB-1) and one sample Book (id 1) from
Assignment 1. These tests use different unique values so they do not collide
with that sample data.
"""

from starlette.testclient import TestClient


def test_memory_backend_starts_with_the_sample_member(
    memory_client: TestClient,
    member_headers: dict[str, str],
) -> None:
    """A new in-memory application exposes the documented sample Member."""
    response = memory_client.get("/members", headers=member_headers)

    assert response.status_code == 200
    assert [member["membership_id"] for member in response.json()] == ["LIB-1"]


def test_member_crud_works_with_memory_client(
    memory_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """The Member router works when DI selects the in-memory service."""
    create_response = memory_client.post(
        "/members",
        json={
            "name": "Grace Hopper",
            "email": "grace@example.com",
            "membership_id": "LIB-2",
            "phone": "555-222-3333",
        },
        headers=admin_headers,
    )

    assert create_response.status_code == 201
    member = create_response.json()
    assert member["id"] == 2

    get_response = memory_client.get(f"/members/{member['id']}", headers=admin_headers)
    assert get_response.status_code == 200
    assert get_response.json() == member

    replace_response = memory_client.put(
        f"/members/{member['id']}",
        json={
            "name": "Rear Admiral Grace Hopper",
            "email": "grace@example.com",
            "membership_id": "LIB-2",
            "phone": "555-222-3333",
        },
        headers=admin_headers,
    )
    assert replace_response.status_code == 200
    assert replace_response.json()["name"] == "Rear Admiral Grace Hopper"

    delete_response = memory_client.delete(
        f"/members/{member['id']}", headers=admin_headers
    )
    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert (
        memory_client.get(f"/members/{member['id']}", headers=admin_headers).status_code
        == 404
    )


def test_member_books_route_works_with_memory_client(
    memory_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """The memory services preserve the Member-to-Book relationship."""
    response = memory_client.get("/members/1/books", headers=admin_headers)

    assert response.status_code == 200
    assert [book["isbn"] for book in response.json()] == ["978-0135957059"]


def test_memory_backend_blocks_deleting_a_member_with_books(
    memory_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """The blocked-deletion rule behaves the same as the database backend."""
    response = memory_client.delete("/members/1", headers=admin_headers)

    assert response.status_code == 409
    assert memory_client.get("/members/1", headers=admin_headers).status_code == 200

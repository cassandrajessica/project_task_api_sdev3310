"""Conformance tests for the documented authentication and authorization contract."""

import pytest
from starlette.testclient import TestClient


# OPENAPI SECURITY SCHEME
# HTTPBearer adds the reusable scheme to OpenAPI. The protected route
# dependencies add a security requirement to each resource operation.


def test_openapi_declares_the_bearer_authentication_scheme(
    database_client: TestClient,
) -> None:
    """API clients can discover the Bearer scheme from the public contract."""
    document = database_client.get("/openapi.json").json()
    scheme = document["components"]["securitySchemes"]["BearerAuthentication"]

    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"


@pytest.mark.parametrize(
    ("path", "method", "expected_statuses"),
    [
        ("/members", "get", {"200", "401"}),
        ("/members", "post", {"201", "401", "403", "409", "422"}),
        ("/members/{member_id}", "get", {"200", "401", "404", "422"}),
        ("/members/{member_id}", "put", {"200", "401", "403", "404", "409", "422"}),
        ("/members/{member_id}", "delete", {"204", "401", "403", "404", "409", "422"}),
        ("/members/{member_id}/books", "get", {"200", "401", "404", "422"}),
        ("/books", "get", {"200", "401"}),
        ("/books", "post", {"201", "401", "403", "404", "409", "422"}),
        ("/books/{book_id}", "get", {"200", "401", "404", "422"}),
        ("/books/{book_id}", "put", {"200", "401", "403", "404", "409", "422"}),
        ("/books/{book_id}", "delete", {"204", "401", "403", "404", "422"}),
    ],
)
def test_openapi_marks_resource_operations_as_bearer_protected(
    database_client: TestClient,
    path: str,
    method: str,
    expected_statuses: set[str],
) -> None:
    """Every Book and Member operation publishes Bearer security and outcomes."""
    operation = database_client.get("/openapi.json").json()["paths"][path][method]

    assert operation["security"] == [{"BearerAuthentication": []}]
    assert expected_statuses <= set(operation["responses"])


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/members", "get"),
        ("/members/{member_id}/books", "get"),
        ("/books", "get"),
        ("/books/{book_id}", "get"),
    ],
)
def test_openapi_read_operations_do_not_document_403(
    database_client: TestClient,
    path: str,
    method: str,
) -> None:
    """Reads are open to both roles, so they document 401 but never 403."""
    operation = database_client.get("/openapi.json").json()["paths"][path][method]

    assert "401" in operation["responses"]
    assert "403" not in operation["responses"]


@pytest.mark.parametrize("path", ["/", "/health"])
def test_openapi_leaves_public_operations_without_security(
    database_client: TestClient,
    path: str,
) -> None:
    """Root and health publish no security requirement, matching runtime."""
    operation = database_client.get("/openapi.json").json()["paths"][path]["get"]

    assert "security" not in operation
    assert "401" not in operation["responses"]


def test_documented_401_matches_the_runtime_challenge(
    database_client: TestClient,
) -> None:
    """The WWW-Authenticate header documented for 401 is actually returned."""
    document = database_client.get("/openapi.json").json()
    documented = document["paths"]["/books"]["get"]["responses"]["401"]

    response = database_client.get("/books")

    assert "WWW-Authenticate" in documented["headers"]
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

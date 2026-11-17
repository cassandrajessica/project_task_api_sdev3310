"""Conformance tests for the public OpenAPI contract.

These tests begin from what an API consumer can see: `/openapi.json`, response
status codes, and JSON bodies. They supplement the integration tests that
exercise successful workflows in detail.
"""

from typing import Any

import pytest
import schemathesis
from openapi_spec_validator import validate
from starlette.testclient import TestClient


# OPENAPI DOCUMENT VALIDATION


# OPENAPI-SPEC-VALIDATOR TEST
# This is the one direct use of openapi-spec-validator in this project. It
# checks whether the complete generated OpenAPI document is structurally valid.
def test_generated_openapi_document_is_valid(database_client: TestClient) -> None:
    """The API publishes a structurally valid OpenAPI document."""
    response = database_client.get("/openapi.json")

    assert response.status_code == 200
    openapi_document = response.json()
    # The validator raises an exception if FastAPI generated an invalid OpenAPI
    # document. It validates the complete document, not a single data schema.
    validate(openapi_document)


# APPROVED CONTRACT ASSERTIONS
# These ordinary pytest tests protect the paths, methods, status codes, and
# component schemas that API consumers are expected to depend on.


def test_openapi_document_declares_the_approved_public_operations(
    database_client: TestClient,
) -> None:
    """Required paths, methods, and successful/error outcomes stay published."""
    openapi_document = database_client.get("/openapi.json").json()
    paths = openapi_document["paths"]

    expected_statuses = {
        "/": {"get": {"200"}},
        "/health": {"get": {"200"}},
        "/members": {"get": {"200"}, "post": {"201", "409", "422"}},
        "/members/{member_id}": {
            "get": {"200", "404", "422"},
            "put": {"200", "404", "409", "422"},
            "delete": {"204", "404", "409", "422"},
        },
        "/members/{member_id}/books": {"get": {"200", "404", "422"}},
        "/books": {"get": {"200"}, "post": {"201", "404", "409", "422"}},
        "/books/{book_id}": {
            "get": {"200", "404", "422"},
            "put": {"200", "404", "409", "422"},
            "delete": {"204", "404", "422"},
        },
    }

    for path, operations in expected_statuses.items():
        assert path in paths
        for method, statuses in operations.items():
            assert method in paths[path]
            documented_statuses = set(paths[path][method]["responses"])
            assert statuses <= documented_statuses


def test_openapi_document_describes_member_and_book_schemas(
    database_client: TestClient,
) -> None:
    """Pydantic request and response rules appear in the public contract."""
    openapi_document = database_client.get("/openapi.json").json()
    schemas = openapi_document["components"]["schemas"]

    member_fields = {"name", "email", "membership_id", "phone"}
    book_fields = {"title", "author", "isbn", "published_year", "member_id"}
    assert_schema_fields(schemas["MemberInput"], member_fields)
    assert_schema_fields(schemas["MemberResponse"], member_fields | {"id"})
    assert_schema_fields(schemas["BookInput"], book_fields)
    assert_schema_fields(schemas["BookResponse"], book_fields | {"id"})

    member_properties = schemas["MemberInput"]["properties"]
    assert member_properties["name"]["minLength"] == 1
    assert member_properties["name"]["maxLength"] == 120
    assert member_properties["email"]["format"] == "email"
    assert member_properties["phone"]["pattern"]

    book_properties = schemas["BookInput"]["properties"]
    assert book_properties["title"]["maxLength"] == 200
    assert book_properties["published_year"]["minimum"] == 1450
    assert book_properties["member_id"]["exclusiveMinimum"] == 0

    member_post_schema = paths_response_schema(
        openapi_document,
        "/members",
        "post",
        "201",
    )
    book_post_schema = paths_response_schema(
        openapi_document,
        "/books",
        "post",
        "201",
    )
    assert member_post_schema == {"$ref": "#/components/schemas/MemberResponse"}
    assert book_post_schema == {"$ref": "#/components/schemas/BookResponse"}

    member_post_body = openapi_document["paths"]["/members"]["post"]["requestBody"]
    assert member_post_body["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/MemberInput"
    }


# TARGETED RESPONSE CONFORMANCE
# These ordinary pytest tests send known requests and confirm their visible
# HTTP behavior matches the important outcomes documented by the API.


def test_create_member_and_book_match_their_documented_responses(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """Created resources have the documented status and response shape."""
    member = create_member(database_client, admin_headers)

    assert set(member) == {"id", "name", "email", "membership_id", "phone"}
    assert isinstance(member["id"], int)
    assert member["id"] > 0

    book = create_book(database_client, admin_headers, member["id"])

    assert set(book) == {
        "id",
        "title",
        "author",
        "isbn",
        "published_year",
        "member_id",
    }
    assert book["member_id"] == member["id"]


def test_missing_member_matches_documented_not_found_response(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """A consumer receives the documented 404 outcome for a missing Member."""
    response = database_client.get("/members/999999", headers=admin_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Member not found"}


def test_member_with_books_matches_documented_conflict_response(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """Deleting a Member with Books returns the documented 409 outcome."""
    member = create_member(database_client, admin_headers)
    create_book(database_client, admin_headers, member["id"])

    response = database_client.delete(f"/members/{member['id']}", headers=admin_headers)

    assert response.status_code == 409
    assert (
        "409"
        in database_client.get("/openapi.json").json()["paths"]["/members/{member_id}"][
            "delete"
        ]["responses"]
    )


# SCHEMA-DRIVEN TESTING WITH SCHEMATHESIS


@pytest.fixture
def openapi_schema(database_client: TestClient) -> Any:
    """Load the contract only after the isolated API is running."""
    # Importing the application only after requesting `database_client`
    # preserves the fixture order: DATABASE_URL already points to
    # Testcontainers.
    from app.main import app

    return schemathesis.openapi.from_asgi("/openapi.json", app)


# SCHEMATHESIS / PYTEST CONNECTION
#
# `openapi_schema` above is a normal pytest fixture. This lazy `schema` object
# tells Schemathesis to request that fixture later, when pytest is running a
# test, not while Python is importing this file. That preserves the setup
# order, where `database_client` first points DATABASE_URL at Testcontainers.
#
# The .include(...) call then limits generated tests to three safe GET routes.
schema = schemathesis.pytest.from_fixture("openapi_schema").include(
    method="GET",
    path_regex=r"^/(health|members|books)$",
)


# `@schema.parametrize()` connects this test function to the lazy schema
# above. Schemathesis resolves `openapi_schema`, creates one `case` argument
# for each selected OpenAPI operation, and runs this function once per case.
# `case` is supplied by Schemathesis, not by a pytest fixture. The member
# token is enough because every selected operation is a read.
@schema.parametrize()
def test_generated_read_only_responses_conform_to_openapi(
    case: Any,
    database_client: TestClient,
    member_headers: dict[str, str],
) -> None:
    """Generated safe requests receive responses valid for their OpenAPI schema."""
    # TestClient sends the generated request directly to the running ASGI app.
    # Schemathesis then checks the status code, headers, and response body
    # against the operation described in `/openapi.json`.
    case.call_and_validate(session=database_client, headers=member_headers)


# HELPERS


def assert_schema_fields(schema: dict[str, Any], expected_fields: set[str]) -> None:
    """Confirm a component is an object with the expected documented fields."""
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == expected_fields
    # Every Member and Book field is required; none has a default value.
    assert set(schema["required"]) == expected_fields


def paths_response_schema(
    openapi_document: dict[str, Any],
    path: str,
    method: str,
    status_code: str,
) -> dict[str, str]:
    """Return one operation's JSON response schema from the OpenAPI document."""
    return openapi_document["paths"][path][method]["responses"][status_code]["content"][
        "application/json"
    ]["schema"]


def create_member(
    database_client: TestClient,
    admin_headers: dict[str, str],
) -> dict[str, Any]:
    """Create the parent Member used by the contract scenarios."""
    response = database_client.post(
        "/members",
        json={
            "name": "Contract Member",
            "email": "contract@example.com",
            "membership_id": "LIB-CONTRACT",
            "phone": "555-123-4567",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


def create_book(
    database_client: TestClient,
    admin_headers: dict[str, str],
    member_id: int,
) -> dict[str, Any]:
    """Create a Book related to the given Member."""
    response = database_client.post(
        "/books",
        json={
            "title": "Contract Book",
            "author": "Contract Author",
            "isbn": "978-0135957059",
            "published_year": 2019,
            "member_id": member_id,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()

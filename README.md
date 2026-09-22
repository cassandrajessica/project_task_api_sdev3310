# Library Management System API

The Library Management System API is a simple backend for tracking the books
that library members have borrowed. Staff can create, view, update, and delete
both Members and Books, and every Book is linked to exactly one Member. A single
Member can have many Books.

This project was built for SDEV 3310, Assignment 1. It applies the REST,
Pydantic, router, HTTP-status, and OpenAPI practices from the Project and Task
Management API to a new pair of related resources: Members and Books. Later
assignments will add database persistence, testing, security, and deployment.

## Requirements

- Python (the version is pinned in `.python-version`)
- [uv](https://docs.astral.sh/uv/) for environment and dependency management

## Setup

Clone the project and switch to the assignment branch:

```bash
git clone https://github.com/cassandrajessica/project_task_api_sdev3310/tree/assignment-1
cd project-task-api
git switch assignment-1
```

Install the dependencies:

```bash
uv sync
```

`uv` installs the correct Python version when needed, creates the virtual
environment, and installs the dependencies recorded in `uv.lock` (including
`email-validator`, which the Member email field relies on).

## Run the API

```bash
uv run uvicorn app.main:app --reload
```

The development server runs at `http://localhost:8000`. `--reload` restarts it
whenever a source file changes.

## Explore the API

The same OpenAPI contract is available three ways:

- `http://localhost:8000/docs` — Swagger UI for exploring and calling endpoints
- `http://localhost:8000/redoc` — ReDoc reference documentation
- `http://localhost:8000/openapi.json` — the machine-readable OpenAPI document

## Endpoints

| Method | URL | Purpose | Success status |
| --- | --- | --- | --- |
| GET | `/` | API introduction | 200 OK |
| GET | `/health` | Health check | 200 OK |
| GET | `/members` | List all members | 200 OK |
| GET | `/members/{member_id}` | Get one member | 200 OK |
| POST | `/members` | Create a member | 201 Created |
| PUT | `/members/{member_id}` | Replace a member | 200 OK |
| DELETE | `/members/{member_id}` | Delete a member | 204 No Content |
| GET | `/members/{member_id}/books` | List a member's books | 200 OK |
| GET | `/books` | List all books | 200 OK |
| GET | `/books/{book_id}` | Get one book | 200 OK |
| POST | `/books` | Create a book | 201 Created |
| PUT | `/books/{book_id}` | Replace a book | 200 OK |
| DELETE | `/books/{book_id}` | Delete a book | 204 No Content |

## Members

Create or replace a Member with this JSON body:

```json
{
  "name": "Ada Lovelace",
  "email": "ada@example.com",
  "membership_id": "LIB-1",
  "phone": "555-123-4567"
}
```

Member validation rules:

- `name` is required and must contain 1–120 characters.
- `email` is required, must be a valid email address, and must be unique.
- `membership_id` is required and must be unique.
- `phone` is required and must be a US phone number. The API accepts an optional
  parenthesized area code and hyphen, dot, or space separators, for example
  `(555) 123-4567`, `555-123-4567`, or `5551234567`.
- Surrounding whitespace is removed before validation.
- Unexpected fields are rejected.

A Member who still has Books cannot be deleted; deleting one returns
409 Conflict. Delete or reassign those Books first.

**Two identifiers, one lookup key.** A Member has both an `id` and a
`membership_id`, and they are not the same thing:

- `id` is an integer the server generates (1, 2, 3, ...). It is the value used
  in every URL, so `GET /members/2` fetches the member whose `id` is 2.
- `membership_id` is a string label such as `LIB-1`. It is stored on the
  member as data, but the API does not look members up by it.

So a request like `GET /members/LIB-1` returns a 422 error, because the
path expects the integer `id`, not the membership label.

**When a member shows a `membership_id` like `LIB-1`, still use their integer
`id` to reference them.** Anywhere you point to a member, in a URL such as
`/members/{id}` or in a Book's `member_id` field, use the plain number from
that member's `id` (for example `2`), never the `LIB-1` label and never a
zero-padded form like `000002`. Run `GET /members` to see each member's `id`.

## Books

Create or replace a Book with this JSON body:

```json
{
  "title": "The Pragmatic Programmer",
  "author": "Andrew Hunt",
  "isbn": "978-0135957059",
  "published_year": 2019,
  "member_id": 1
}
```

Book validation rules:

- `title` is required and must contain 1–200 characters.
- `author` is required and must contain 1–120 characters.
- `isbn` is required and must be unique.
- `published_year` is required and must be between 1450 and the current year.
- `member_id` is required and must reference an existing Member.
- Surrounding whitespace is removed before validation.
- Unexpected fields are rejected.

The `member_id` establishes the relationship between a Book and its Member.
Creating or updating a Book with a `member_id` that does not exist returns
404 Not Found.

## Error responses

- Requesting a Member or Book that does not exist returns 404 Not Found.
- A duplicate `email`, `membership_id`, or `isbn` returns 409 Conflict.
- Deleting a Member that still has Books returns 409 Conflict.
- Missing, incomplete, or invalid data returns 422 Unprocessable Content, with a
  body that identifies which field failed and why.

Try a validation error by sending this to `POST /members`:

```json
{
  "name": "",
  "email": "not-an-email",
  "membership_id": "LIB-2",
  "phone": "555-123-4567"
}
```

## Temporary data

Members and Books are stored in Python lists while the application runs. The
application starts with one sample Member and one sample Book so the endpoints
return data immediately. All changes are lost when the server restarts. This is
intentional for this milestone; Assignment 2 replaces the in-memory lists with a
database.

## Project structure

```
project-task-api/
├── app/
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── members.py
│   │   └── books.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── members.py
│   │   └── books.py
│   ├── __init__.py
│   ├── main.py
│   └── storage.py
├── pyproject.toml
├── uv.lock
├── .python-version
└── README.md
```

Route handlers live in `app/routers/`, and the Pydantic request and response
schemas live in `app/schemas/`. `app/storage.py` holds the shared in-memory
collections, and `app/main.py` creates the FastAPI application and registers the
routers.

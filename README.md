# Library Management System API

The Library Management System API is a backend for tracking the books that
library members have borrowed. Staff can create, view, update, and delete both
Members and Books, and every Book is linked to exactly one Member. A single
Member can have many Books.

This project was built for SDEV 3310. Assignment 1 created the REST API with
Pydantic validation and temporary in-memory storage. Assignment 2 adds
PostgreSQL persistence and reorganizes the code into layers, so Library data
now survives an API restart. Later assignments will add testing, security, and
deployment.

## Requirements

- Python 3.13 (pinned in `.python-version`; `uv` installs it if needed)
- [uv](https://docs.astral.sh/uv/) for environment and dependency management
- [PostgreSQL](https://www.postgresql.org/download/), running locally on the
  default port `5432`

Start PostgreSQL before running the API:

- **macOS (Homebrew):** `brew services start postgresql@18` (use the version
  you installed)
- **Windows:** the installer runs PostgreSQL as a Windows service that starts
  automatically. Check it in the Services app if the API cannot connect.

## Setup

### 1. Clone the project

```bash
git clone https://github.com/cassandrajessica/project_task_api_sdev3310.git
cd project_task_api_sdev3310
git switch assignment-2
```

### 2. Install dependencies

```bash
uv sync
```

`uv` installs the correct Python version when needed, creates the virtual
environment, and installs the dependencies recorded in `uv.lock`, including
SQLAlchemy 2.x, Psycopg, and pydantic-settings.

### 3. Create the database

From the project folder, run the setup script against your local PostgreSQL
server:

```bash
psql -d postgres -f scripts/setup_database.sql
```

On Windows, connect as the `postgres` user created by the installer:

```powershell
psql -U postgres -d postgres -f scripts/setup_database.sql
```

The script creates a `postgres` login role (password `postgres`) if it does not
exist and a `library` database if it does not exist. It never deletes data, so
it is safe to run again. You do not need to create tables yourself; the API
creates the `members` and `books` tables the first time it starts.

### 4. Configure the application

Copy the example settings file:

```bash
cp .env.example .env
```

On Windows PowerShell, use `copy .env.example .env`.

| Setting | Default | Purpose |
| --- | --- | --- |
| `STORAGE_BACKEND` | `database` | `database` stores data in PostgreSQL. `memory` stores data in Python lists that reset when the API stops. |
| `DATABASE_URL` | none | PostgreSQL connection URL. Required when `STORAGE_BACKEND=database`. |
| `DATABASE_ECHO_SQL` | `false` | Set to `true` to print the SQL that SQLAlchemy runs in the terminal. |

The URL in `.env.example` matches the database created by the setup script:

```text
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/library
```

It reads as `driver://username:password@host:port/database`. The
`postgres:postgres` credentials are for local development only and should never
be reused in production. `.env` is listed in `.gitignore` and must not be
committed.

Settings are loaded and validated once when the API starts. An unsupported
`STORAGE_BACKEND` value, or a missing `DATABASE_URL` while the database backend
is selected, stops the API at startup with a clear error.

## Run the API

```bash
uv run uvicorn app.main:app --reload
```

The development server runs at `http://localhost:8000`. `--reload` restarts it
whenever a source file changes. With `DATABASE_ECHO_SQL=true`, the terminal
shows each SQL statement, including `CREATE TABLE` on the first startup.

To confirm the tables exist, run:

```bash
psql -h localhost -U postgres -d library -c '\dt'
```

Enter the password `postgres` if prompted. The result should list `books` and
`members`.

## Explore the API

The same OpenAPI contract is available three ways:

- `http://localhost:8000/docs`: Swagger UI for exploring and calling endpoints
- `http://localhost:8000/redoc`: ReDoc reference documentation
- `http://localhost:8000/openapi.json`: the machine-readable OpenAPI document

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

A new database starts empty, so create a Member before creating Books. Send
this JSON body to `POST /members`:

```json
{
  "name": "Ada Lovelace",
  "email": "ada@example.com",
  "membership_id": "LIB-1",
  "phone": "555-123-4567"
}
```

The response includes the `id` that PostgreSQL generated for the new Member.

Member validation rules:

- `name` is required and must contain 1-120 characters.
- `email` is required, must be a valid email address, and must be unique.
- `membership_id` is required, must contain 1-50 characters, and must be unique.
- `phone` is required and must be a US phone number. The API accepts an optional
  parenthesized area code and hyphen, dot, or space separators, for example
  `(555) 123-4567`, `555-123-4567`, or `5551234567`.
- Surrounding whitespace is removed before validation.
- Unexpected fields are rejected.

Email and membership ID uniqueness is checked by the service layer and also
enforced by unique constraints in PostgreSQL.

A Member who still has Books cannot be deleted; deleting one returns
409 Conflict. Delete or reassign those Books first.

**Two identifiers, one lookup key.** A Member has both an `id` and a
`membership_id`, and they are not the same thing:

- `id` is an integer the database generates (1, 2, 3, ...). It is the value
  used in every URL, so `GET /members/2` fetches the member whose `id` is 2.
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

Use the Member's returned `id` as `member_id`, then send this JSON body to
`POST /books`:

```json
{
  "title": "The Pragmatic Programmer",
  "author": "Andrew Hunt",
  "isbn": "978-0135957059",
  "published_year": 2019,
  "member_id": 1
}
```

Then call `GET /members/1/books` to see the Books associated with that Member.

Book validation rules:

- `title` is required and must contain 1-200 characters.
- `author` is required and must contain 1-120 characters.
- `isbn` is required, must contain 1-20 characters, and must be unique.
- `published_year` is required and must be between 1450 and the current year.
- `member_id` is required and must reference an existing Member.
- Surrounding whitespace is removed before validation.
- Unexpected fields are rejected.

The `member_id` field is a foreign key to the `members` table. Creating or
updating a Book with a `member_id` that does not exist returns 404 Not Found.
ISBN uniqueness is checked by the service layer and also enforced by a unique
constraint in PostgreSQL.

## Error responses

- Requesting a Member or Book that does not exist returns 404 Not Found.
- A duplicate `email`, `membership_id`, or `isbn` returns 409 Conflict.
- Deleting a Member that still has Books returns 409 Conflict.
- Missing, incomplete, or invalid data returns 422 Unprocessable Content, with a
  body that identifies which field failed and why.

Error responses describe the problem without exposing database details. A write
that fails partway through is rolled back, so no partial changes are saved.

Try a validation error by sending this to `POST /members`:

```json
{
  "name": "",
  "email": "not-an-email",
  "membership_id": "LIB-2",
  "phone": "555-123-4567"
}
```

## Verify persistence

With `STORAGE_BACKEND=database`:

1. Create a Member and a Book in Swagger UI.
2. Stop the server with `Ctrl+C` and start it again.
3. Call `GET /members` and `GET /books`. The records you created are still
   there.

## Storage backends

Set `STORAGE_BACKEND` in `.env` to choose where data is stored. Restart the API
after changing it.

| Backend | Where data lives | After a restart |
| --- | --- | --- |
| `database` (default) | PostgreSQL `library` database | Data is kept. A new database starts empty. |
| `memory` | Python lists inside the running process | Data resets to one sample Member and one sample Book. |

Both backends implement the same service contracts, so every endpoint behaves
the same way. The memory backend is useful for quick experiments without
PostgreSQL. Its data is not shared between processes.

## Application layers

```text
HTTP request
    ↓
Router         HTTP details, Pydantic schemas, and status codes
    ↓
Service        Library business rules and transaction decisions
    ↓
Repository     SQLAlchemy queries and writes
    ↓
PostgreSQL     durable Members and Books
```

| Layer | Location | Responsibility |
| --- | --- | --- |
| Routers | `app/routers/` | Receive validated requests, call a service, and convert service exceptions into HTTP responses. |
| Schemas | `app/schemas/` | Define the API contract: request validation and response shapes. |
| Services | `app/services/` | Apply Library rules such as uniqueness, related-Member checks, and blocked Member deletion. Each resource has an abstract contract plus database and in-memory implementations. |
| Repositories | `app/repositories/` | Run SQLAlchemy queries and writes for one table. |
| ORM models | `app/models/` | Define the `members` and `books` tables, constraints, and relationship. |
| Database and configuration | `app/database/`, `app/config.py` | Create the engine and session factory and load typed settings. |

At startup, `app/main.py` reads the settings, creates the services for the
selected backend, and stores them on application state. Routes receive them
through FastAPI dependencies in `app/dependencies.py`, so they depend on the
service contract instead of on PostgreSQL or Python lists.

The application creates one SQLAlchemy engine and one session factory. Each
database service operation opens its own short-lived Session. Write operations
use `session_factory.begin()`, which commits when the operation completes and
rolls back if an exception occurs, so a use case that checks several records and
then writes is saved completely or not at all.

## Project structure

```
project_task_api_sdev3310/
├── app/
│   ├── database/
│   │   ├── __init__.py
│   │   └── session.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── book.py
│   │   └── member.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── books.py
│   │   └── members.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── books.py
│   │   ├── http_errors.py
│   │   └── members.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── books.py
│   │   └── members.py
│   ├── services/
│   │   ├── books/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── database.py
│   │   │   └── in_memory.py
│   │   ├── members/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── database.py
│   │   │   └── in_memory.py
│   │   ├── __init__.py
│   │   └── in_memory_store.py
│   ├── __init__.py
│   ├── config.py
│   ├── dependencies.py
│   ├── exceptions.py
│   └── main.py
├── scripts/
│   └── setup_database.sql
├── .env.example
├── .gitignore
├── .python-version
├── pyproject.toml
├── uv.lock
└── README.md
```

- `app/exceptions.py` defines the application outcomes services raise, such as
  a missing Member or a duplicate ISBN.
- `app/routers/http_errors.py` converts those outcomes into HTTP responses.
- `app/services/in_memory_store.py` holds the shared lists and lock used by the
  memory backend.
- `scripts/setup_database.sql` creates the local PostgreSQL role and database.

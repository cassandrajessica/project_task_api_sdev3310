"""FastAPI application for the Library Management System API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  # Register ORM models before create_all().
from app.config import Settings, StorageBackend
from app.database.session import create_database
from app.models.base import Base
from app.routers.books import router as books_router
from app.routers.members import router as members_router
from app.services.books import DatabaseBookService, InMemoryBookService
from app.services.in_memory_store import InMemoryStore
from app.services.members import DatabaseMemberService, InMemoryMemberService

# Tag descriptions organize related operations and explain each resource group
# in Swagger UI and ReDoc.
tags_metadata = [
    {
        "name": "General",
        "description": "Basic application information and health checks.",
    },
    {
        "name": "Members",
        "description": "Create and manage members and view their related books.",
    },
    {
        "name": "Books",
        "description": "Create and manage books that belong to members.",
    },
]


# Missing tables are created at startup. Database migrations are introduced in
# a later module.
@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize application-scoped infrastructure at startup."""
    settings = Settings()
    application.state.settings = settings

    if settings.storage_backend is StorageBackend.MEMORY:
        # Both services share one store so Book checks can see Members.
        store = InMemoryStore()
        application.state.member_service = InMemoryMemberService(store)
        application.state.book_service = InMemoryBookService(store)
    elif settings.storage_backend is StorageBackend.DATABASE:
        database = create_database(settings)
        Base.metadata.create_all(bind=database.engine)
        # Services are stateless and safe to share. They receive the session
        # factory, not one shared Session, so each database operation creates
        # its own unit of work and controls its own transaction.
        application.state.member_service = DatabaseMemberService(
            database.session_factory
        )
        application.state.book_service = DatabaseBookService(
            database.session_factory
        )
    # Code after yield would run during application shutdown.
    yield


# Create the FastAPI application object that Uvicorn will load and run.
app = FastAPI(
    title="Library Management System API",
    description=(
        "Manage library members and the books they have borrowed. Data is "
        "stored in PostgreSQL by default, with an in-memory option for "
        "temporary local use."
    ),
    version="0.2.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

# Add every Member and Book route to the application. Keeping resource routes
# in routers prevents main.py from becoming crowded.
app.include_router(members_router)
app.include_router(books_router)


# This decorator connects an HTTP GET request for "/" to read_root().
@app.get("/", tags=["General"], summary="Introduce the API")
def read_root() -> dict[str, str]:
    """Return a short introduction to the API."""
    # FastAPI converts the returned Python dictionary into a JSON response.
    return {"message": "Library Management System API"}


# The health endpoint gives clients a simple way to confirm the API is running.
@app.get("/health", tags=["General"], summary="Check API health")
def health_check() -> dict[str, str]:
    """Confirm that the API process is running."""
    # A successful request receives HTTP 200 and this JSON response body.
    return {"status": "healthy"}

"""FastAPI application for the Library Management System API."""

from fastapi import FastAPI

from app.routers.members import router as members_router
from app.routers.books import router as books_router


tags_metadata = [
    {
        "name": "General",
        "description": "Basic application information.",
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

# Create the FastAPI application object that Uvicorn will load and run.
app = FastAPI(
    title="Library Management System API",
    description="Manage members and their associated books.",
    version="0.1.0",
    openapi_tags=tags_metadata,
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
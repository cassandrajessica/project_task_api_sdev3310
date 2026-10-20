"""Application outcomes raised by services without depending on FastAPI."""


class MemberNotFoundError(Exception):
    """Signal that the requested Member does not exist.

    This exception remains outside the router package so the service can be
    reused by HTTP routes, jobs, or message consumers without importing FastAPI.
    """


class BookNotFoundError(Exception):
    """Signal that the requested Book does not exist."""


class MemberHasBooksError(Exception):
    """Signal that a Member cannot be deleted while Books reference it."""


class MemberEmailAlreadyExistsError(Exception):
    """Signal that another Member already uses this email address."""


class MembershipIdAlreadyExistsError(Exception):
    """Signal that another Member already uses this membership ID."""


class IsbnAlreadyExistsError(Exception):
    """Signal that another Book already uses this ISBN."""

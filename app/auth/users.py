"""Predefined classroom users and roles for Assignment 3.

This module intentionally does not model a production user store. It maps two
environment-configured classroom tokens to fixed identities and roles so the
authentication and authorization request flow remains easy to inspect.

These request roles are separate from the Member records stored by the
Library. A "member" role is a caller who may read Library data; it is not a
row in the members table.
"""

from dataclasses import dataclass
from enum import Enum

from app.config import Settings


class Role(str, Enum):
    """Roles supported by the simple classroom permission policy."""

    MEMBER = "member"
    ADMIN = "admin"


@dataclass(frozen=True)
class AuthenticatedUser:
    """Represent the identity and role established by a valid Bearer token."""

    username: str
    role: Role


def get_demo_token_for_role(role: Role, settings: Settings) -> str:
    """Return the validated classroom token configured for one role."""
    if role is Role.MEMBER:
        return settings.demo_member_token
    return settings.demo_admin_token


def get_user_for_token(token: str, settings: Settings) -> AuthenticatedUser | None:
    """Map one configured classroom token to its predefined user and role."""
    member_token = get_demo_token_for_role(Role.MEMBER, settings)
    admin_token = get_demo_token_for_role(Role.ADMIN, settings)

    # Empty environment values must not accidentally authenticate an empty
    # credential. An empty string is therefore treated as unconfigured.
    if member_token and token == member_token:
        return AuthenticatedUser(username="member", role=Role.MEMBER)
    if admin_token and token == admin_token:
        return AuthenticatedUser(username="admin", role=Role.ADMIN)
    return None

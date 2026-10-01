"""Object-level authorization rules shared by domain services."""

from uuid import UUID

from app.core.errors import NotFoundError
from app.models.user import User


def ensure_resource_visible(resource_owner_id: UUID, current_user: User) -> None:
    """Raise ``NOT_FOUND`` when a client cannot see another client's resource.

    Operational users have global visibility. Returning ``404`` rather than
    ``403`` for another client's resource avoids disclosing its existence.
    """
    if current_user.role == "client" and current_user.id != resource_owner_id:
        raise NotFoundError()

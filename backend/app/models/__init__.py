"""
SQLAlchemy models for the Dataset Request Desk.

All models inherit from Base and follow the schema defined in docs/DATA_MODEL.md.
Import from this module to ensure all models are registered with SQLAlchemy.
"""

from app.models.assignment import Assignment
from app.models.episode import Episode
from app.models.refresh_token import RefreshToken
from app.models.request import Request
from app.models.request_status_history import RequestStatusHistory
from app.models.user import User

__all__ = [
    "Assignment",
    "Episode",
    "RefreshToken",
    "Request",
    "RequestStatusHistory",
    "User",
]

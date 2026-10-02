"""Text helpers for user-supplied string input."""


def escape_like(value: str) -> str:
    """Escape LIKE/ILIKE metacharacters so user input matches literally.

    Postgres uses backslash as the default escape character. Callers must
    pass ``escape="\\"`` to SQLAlchemy's ``.ilike()`` for this to apply.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

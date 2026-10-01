class AppError(Exception):
    """Base exception for expected application errors."""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.field = field


class AuthenticationRequiredError(AppError):
    def __init__(
        self,
        message: str = "Authentication required",
    ) -> None:
        super().__init__(
            code="AUTHENTICATION_REQUIRED",
            message=message,
            http_status=401,
        )


class InvalidCredentialsError(AppError):
    def __init__(
        self,
        message: str = "Invalid credentials",
    ) -> None:
        super().__init__(
            code="INVALID_CREDENTIALS",
            message=message,
            http_status=401,
        )


class ForbiddenError(AppError):
    def __init__(
        self,
        message: str = "Forbidden",
    ) -> None:
        super().__init__(
            code="FORBIDDEN",
            message=message,
            http_status=403,
        )


class NotFoundError(AppError):
    def __init__(
        self,
        message: str = "Resource not found",
    ) -> None:
        super().__init__(
            code="NOT_FOUND",
            message=message,
            http_status=404,
        )


class ValidationError(AppError):
    def __init__(
        self,
        message: str = "Validation error",
        field: str | None = None,
    ) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            http_status=422,
            field=field,
        )


class InvalidCursorError(AppError):
    def __init__(
        self,
        message: str = "Invalid cursor",
    ) -> None:
        super().__init__(
            code="INVALID_CURSOR",
            message=message,
            http_status=400,
        )


class InvalidTransitionError(AppError):
    def __init__(
        self,
        message: str,
        field: str | None = None,
    ) -> None:
        super().__init__(
            code="INVALID_STATUS_TRANSITION",
            message=message,
            http_status=409,
            field=field,
        )


class InsufficientEpisodesError(AppError):
    def __init__(
        self,
        message: str = "Insufficient episodes",
    ) -> None:
        super().__init__(
            code="INSUFFICIENT_EPISODES",
            message=message,
            http_status=409,
        )


class ImportError(AppError):
    def __init__(
        self,
        message: str = "Import failed",
    ) -> None:
        super().__init__(
            code="IMPORT_ERROR",
            message=message,
            http_status=400,
        )


class InternalError(AppError):
    def __init__(
        self,
        message: str = "Internal server error",
    ) -> None:
        super().__init__(
            code="INTERNAL_ERROR",
            message=message,
            http_status=500,
        )
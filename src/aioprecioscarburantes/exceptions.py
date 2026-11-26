"""Exceptions for aioprecioscarburantes."""


class PreciosCarburantesError(Exception):
    """Generic error."""


class PreciosCarburantesConnectionError(PreciosCarburantesError):
    """The API could not be reached or returned an invalid response."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        """Initialize with the HTTP status, if the server answered with an error."""
        super().__init__(message)
        self.status = status


class PreciosCarburantesNotFoundError(PreciosCarburantesError):
    """The requested item does not exist."""

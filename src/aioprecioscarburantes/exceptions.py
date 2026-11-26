"""Exceptions for aioprecioscarburantes."""


class PreciosCarburantesError(Exception):
    """Generic error."""


class PreciosCarburantesConnectionError(PreciosCarburantesError):
    """The API could not be reached or returned an invalid response."""


class PreciosCarburantesNotFoundError(PreciosCarburantesError):
    """The requested item does not exist."""

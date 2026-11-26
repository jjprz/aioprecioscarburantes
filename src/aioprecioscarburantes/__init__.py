"""Async client for Spanish fuel prices (Ministerio, PreciosCarburantes)."""

from .client import PreciosCarburantes
from .exceptions import (
    PreciosCarburantesConnectionError,
    PreciosCarburantesError,
    PreciosCarburantesNotFoundError,
)
from .models import FuelType, Municipality, Province, SaleType, Station, StationList

__all__ = [
    "FuelType",
    "Municipality",
    "PreciosCarburantes",
    "PreciosCarburantesConnectionError",
    "PreciosCarburantesError",
    "PreciosCarburantesNotFoundError",
    "Province",
    "SaleType",
    "Station",
    "StationList",
]

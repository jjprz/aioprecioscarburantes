"""Async client for the Spanish fuel prices API (PreciosCarburantes)."""

from __future__ import annotations

import asyncio
import json
import ssl
from typing import TYPE_CHECKING, Any, Self

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout

from .exceptions import (
    PreciosCarburantesConnectionError,
    PreciosCarburantesError,
    PreciosCarburantesNotFoundError,
)
from .models import Municipality, Province, Station, StationList

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

BASE_URL = (
    "https://sedeaplicaciones.minetur.gob.es"
    "/ServiciosRESTCarburantes/PreciosCarburantes"
)
# The Ministry's server sometimes only accepts AES256-GCM-SHA384 (RSA key
# exchange), which Python's default context leaves out. It was seen on
# 26 November 2026, for a few hours at a time. When a request to that server
# fails to connect, it is retried with this context, which also allows that
# cipher; the server still picks a modern one when it offers it. Built at import
# time, because loading the certificates blocks.
LEGACY_SSL_CONTEXT = ssl.create_default_context()
LEGACY_SSL_CONTEXT.set_ciphers("DEFAULT:AES256-GCM-SHA384")

# Undocumented API used by the geoportalgasolineras.es website. It also lists
# stations with restricted sales, which the official service leaves out.
GEOPORTAL_URL = "https://geoportalgasolineras.es/rest"


def _parse[T](build: Callable[[], T]) -> T:
    """Build models, turning an unexpected response format into an API error."""
    try:
        return build()
    except (KeyError, TypeError, ValueError, AttributeError) as err:
        raise PreciosCarburantesError(
            f"Unexpected response from the fuel prices API: {err!r}"
        ) from err


class PreciosCarburantes:
    """Client for the Spanish Ministry fuel prices REST service."""

    def __init__(
        self,
        session: ClientSession | None = None,
        *,
        request_timeout: float = 30,
        base_url: str = BASE_URL,
        geoportal_url: str = GEOPORTAL_URL,
        retries: int = 1,
        retry_delay: float = 2,
    ) -> None:
        """Initialize; pass a session to share it (as Home Assistant does)."""
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._geoportal_url = geoportal_url.rstrip("/")
        self._retries = retries
        self._retry_delay = retry_delay
        # Set once the legacy context was needed, to use it first from then on
        self._prefer_legacy = False
        self._close_session = False
        self._timeout = ClientTimeout(total=request_timeout)

    async def _request(self, path: str, *, base_url: str | None = None) -> Any:
        """Request a path, retrying once after a connection error.

        The Ministry's server sometimes drops a single request; a short retry
        avoids leaving stations without prices until the next update.
        """
        for attempt in range(self._retries + 1):
            # Retries to the Ministry's server also allow its legacy cipher
            legacy = base_url is None and (attempt > 0 or self._prefer_legacy)
            try:
                data = await self._request_once(path, base_url=base_url, legacy=legacy)
            except PreciosCarburantesConnectionError as err:
                if attempt == self._retries or (
                    err.status is not None and err.status < 500
                ):
                    raise
                await asyncio.sleep(self._retry_delay)
            else:
                if legacy:
                    self._prefer_legacy = True
                return data
        raise AssertionError  # pragma: no cover

    async def _request_once(
        self, path: str, *, base_url: str | None, legacy: bool = False
    ) -> Any:
        """Request a path and return the decoded JSON (None if empty)."""
        if self._session is None:
            self._session = ClientSession()
            self._close_session = True
        try:
            async with self._session.get(
                f"{base_url or self._base_url}/{path}",
                timeout=self._timeout,
                headers={"Accept": "application/json"},
                ssl=LEGACY_SSL_CONTEXT if legacy else True,
            ) as response:
                response.raise_for_status()
                text = await response.text()
                data = json.loads(text) if text.strip() else None
        except TimeoutError as err:
            raise PreciosCarburantesConnectionError(
                "Timeout while connecting to the fuel prices API"
            ) from err
        except ClientResponseError as err:
            raise PreciosCarburantesConnectionError(
                f"Fuel prices API returned HTTP {err.status}", status=err.status
            ) from err
        except (ClientError, ValueError) as err:
            raise PreciosCarburantesConnectionError(
                "Error communicating with the fuel prices API"
            ) from err
        if isinstance(data, dict) and data.get("ResultadoConsulta", "OK") != "OK":
            raise PreciosCarburantesError(
                f"Fuel prices API error: {data['ResultadoConsulta']}"
            )
        return data

    async def get_provinces(self) -> list[Province]:
        """Return all provinces."""
        data = await self._request("Listados/Provincias/")
        return _parse(lambda: [Province.from_api(item) for item in data])

    async def get_municipalities(self, province_id: str) -> list[Municipality]:
        """Return the municipalities of a province."""
        data = await self._request(f"Listados/MunicipiosPorProvincia/{province_id}")
        return _parse(lambda: [Municipality.from_api(item) for item in data])

    async def get_stations_by_municipality(self, municipality_id: str) -> StationList:
        """Return the stations and prices of a municipality."""
        data = await self._request(
            f"EstacionesTerrestres/FiltroMunicipio/{municipality_id}"
        )
        return _parse(lambda: StationList.from_api(data))

    async def get_stations_by_province(self, province_id: str) -> StationList:
        """Return the stations and prices of a province."""
        data = await self._request(
            f"EstacionesTerrestres/FiltroProvincia/{province_id}"
        )
        return _parse(lambda: StationList.from_api(data))

    async def get_station(self, municipality_id: str, station_id: str) -> Station:
        """Return one station (the API has no per-station query)."""
        result = await self.get_stations_by_municipality(municipality_id)
        for station in result.stations:
            if station.id == station_id:
                return station
        raise PreciosCarburantesNotFoundError(
            f"Station {station_id} not found in municipality {municipality_id}"
        )

    async def get_station_by_id(self, station_id: str) -> Station:
        """Return any station by its id, also those with restricted sales.

        Uses the undocumented Geoportal web API, which may change without notice.
        The returned station has no municipality or province ids.
        """
        data = await self._request(
            f"{station_id}/busquedaEstacionPrecio", base_url=self._geoportal_url
        )
        if not data or str(data.get("eessId")) != str(station_id):
            raise PreciosCarburantesNotFoundError(f"Station {station_id} not found")
        return _parse(lambda: Station.from_geoportal(data))

    async def close(self) -> None:
        """Close the session if it was created here."""
        if self._session is not None and self._close_session:
            await self._session.close()

    async def __aenter__(self) -> Self:
        """Enter the async context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit the async context."""
        await self.close()

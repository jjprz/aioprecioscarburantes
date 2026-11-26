"""Check the real services still answer as the library expects.

Run daily by the "Smoke test" workflow. Fails if the data cannot be read; prints
a warning annotation if the Ministry's server needed the legacy cipher.
"""

import asyncio
import contextlib
import ssl

import aiohttp

from aioprecioscarburantes import FuelType, PreciosCarburantes
from aioprecioscarburantes.client import BASE_URL

MUNICIPALITY_ID = "4469"  # Antequera, about 20 stations
STATION_ID = "9683"  # A cooperative with restricted sales, only on the Geoportal


async def default_cipher_works() -> bool:
    """Return if the Ministry's server accepts Python's default context."""
    host = BASE_URL.split("/")[2]
    try:
        _, writer = await asyncio.open_connection(
            host, 443, ssl=ssl.create_default_context()
        )
    except (OSError, ssl.SSLError):
        return False
    writer.close()
    # The handshake worked; a slow close does not matter
    with contextlib.suppress(OSError, TimeoutError):
        await asyncio.wait_for(writer.wait_closed(), 5)
    return True


async def main() -> None:
    """Fetch provinces, a municipality and a station by code."""
    async with aiohttp.ClientSession() as session:
        client = PreciosCarburantes(session=session)
        provinces = await client.get_provinces()
        assert len(provinces) >= 50, f"only {len(provinces)} provinces"
        municipalities = await client.get_municipalities("29")
        assert municipalities, "no municipalities in Málaga"
        result = await client.get_stations_by_municipality(MUNICIPALITY_ID)
        assert result.stations, "no stations in the municipality"
        prices = [station.prices for station in result.stations]
        assert any(FuelType.DIESEL_A in p for p in prices), "no diesel prices"
        station = await client.get_station_by_id(STATION_ID)
        assert station.prices, "the station by code has no prices"
    print(
        f"OK: {len(provinces)} provinces, {len(result.stations)} stations, "
        f"updated {result.updated_at:%Y-%m-%d %H:%M}"
    )
    if not await default_cipher_works():
        print(
            "::warning::The Ministry's server rejects the default cipher; "
            "the legacy fallback was needed"
        )


asyncio.run(main())

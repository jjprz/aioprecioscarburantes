# aioprecioscarburantes

Async Python client for Spanish fuel prices, from the Spanish Ministry's
official `PreciosCarburantes` REST service (the data behind Geoportal Gasolineras).
No API key needed. Prices are updated every 30 minutes.

```python
import asyncio
from aioprecioscarburantes import FuelType, PreciosCarburantes


async def main() -> None:
    async with PreciosCarburantes() as client:
        result = await client.get_stations_by_municipality("6139")
        for station in result.stations:
            print(station.brand, station.prices.get(FuelType.DIESEL_A))


asyncio.run(main())
```

Methods: `get_provinces()`, `get_municipalities(province_id)`,
`get_stations_by_municipality(municipality_id)`,
`get_stations_by_province(province_id)`, `get_station(municipality_id, station_id)`.
Pass an existing `aiohttp.ClientSession` to share it.

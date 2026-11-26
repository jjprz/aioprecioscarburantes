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

### Stations with restricted sales

The official service leaves out stations that only sell to members or fleets
(e.g. agricultural cooperatives). `get_station_by_id(station_id)` reads any
station, restricted ones included, from the API behind the
[Geoportal Gasolineras](https://geoportalgasolineras.es) website. That API is
undocumented and may change without notice; the station it returns has no
municipality or province ids.

### Opening hours

`parse_schedule(station.schedule)` understands the Ministry's opening hours
("L-D: 24H", "L-S: 07:00-22:00; D: 08:00-14:00", "L-V: 07:00-14:00 y 16:00-21:00"…)
and returns a `Schedule` with `is_open(datetime)`; `next_change(schedule, datetime)`
gives the next opening or closing. Unknown or ambiguous formats return `None`.

### TLS note

Since November 2026 the Ministry's server only accepts the `AES256-GCM-SHA384`
cipher, which Python's default SSL context does not offer. The client allows it,
on top of the defaults, for requests to that server only.

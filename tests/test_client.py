"""Tests for aioprecioscarburantes."""

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from aioprecioscarburantes import (
    FuelType,
    PreciosCarburantes,
    PreciosCarburantesConnectionError,
    PreciosCarburantesError,
    PreciosCarburantesNotFoundError,
    SaleType,
)
from aioprecioscarburantes.models import TIMEZONE

FIXTURES = Path(__file__).parent / "fixtures"
ServerFactory = Callable[[web.Application], Awaitable[TestServer]]


def load(name: str) -> Any:
    """Load a fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def make_client(
    aiohttp_server: ServerFactory,
    routes: dict[str, web.Response | Callable[[], web.Response]],
) -> PreciosCarburantes:
    """Start a fake API answering the given paths."""
    app = web.Application()
    for path, reply in routes.items():

        async def handler(_: web.Request, reply: Any = reply) -> web.Response:
            response: web.Response = reply() if callable(reply) else reply
            return response

        app.router.add_get(f"/{path}", handler)
    server = await aiohttp_server(app)
    return PreciosCarburantes(
        base_url=str(server.make_url("")), request_timeout=1, retry_delay=0
    )


def json_reply(name: str) -> Callable[[], web.Response]:
    """Reply with a fixture."""
    return lambda: web.json_response(load(name))


async def test_provinces(aiohttp_server: ServerFactory) -> None:
    """Provinces are parsed, including the misspelt id key."""
    client = await make_client(
        aiohttp_server, {"Listados/Provincias/": json_reply("provincias.json")}
    )
    async with client:
        provinces = await client.get_provinces()
    assert provinces[0].id == "02"
    assert provinces[0].name == "ALBACETE"


async def test_municipalities(aiohttp_server: ServerFactory) -> None:
    """Municipalities are parsed."""
    client = await make_client(
        aiohttp_server,
        {"Listados/MunicipiosPorProvincia/41": json_reply("municipios.json")},
    )
    async with client:
        municipalities = await client.get_municipalities("41")
    assert municipalities[0].province_id == "41"


async def test_stations(aiohttp_server: ServerFactory) -> None:
    """Stations are parsed with decimal commas and only sold fuels."""
    client = await make_client(
        aiohttp_server,
        {"EstacionesTerrestres/FiltroMunicipio/6139": json_reply("estaciones.json")},
    )
    async with client:
        result = await client.get_stations_by_municipality("6139")
    assert result.updated_at.tzinfo == TIMEZONE
    repsol = result.stations[0]
    assert repsol.id == "7370"
    assert repsol.brand == "REPSOL"
    assert repsol.sale_type is SaleType.PUBLIC
    assert repsol.latitude == pytest.approx(37.214444)
    assert repsol.prices[FuelType.DIESEL_A] == pytest.approx(1.825)
    assert FuelType.HYDROGEN not in repsol.prices


async def test_get_station(aiohttp_server: ServerFactory) -> None:
    """One station is found, or a not-found error is raised."""
    client = await make_client(
        aiohttp_server,
        {"EstacionesTerrestres/FiltroMunicipio/6139": json_reply("estaciones.json")},
    )
    async with client:
        assert (await client.get_station("6139", "6440")).brand == "SHELL"
        with pytest.raises(PreciosCarburantesNotFoundError):
            await client.get_station("6139", "1")


async def test_province_stations(aiohttp_server: ServerFactory) -> None:
    """The province endpoint is used."""
    client = await make_client(
        aiohttp_server,
        {"EstacionesTerrestres/FiltroProvincia/41": json_reply("estaciones.json")},
    )
    async with client:
        result = await client.get_stations_by_province("41")
    assert len(result.stations) == 2


@pytest.mark.parametrize(
    "reply",
    [
        lambda: web.Response(status=500),
        lambda: web.Response(text="no json"),
    ],
)
async def test_connection_errors(
    aiohttp_server: ServerFactory, reply: Callable[[], web.Response]
) -> None:
    """HTTP errors and bad JSON become connection errors."""
    client = await make_client(aiohttp_server, {"Listados/Provincias/": reply})
    async with client:
        with pytest.raises(PreciosCarburantesConnectionError):
            await client.get_provinces()


async def test_unreachable() -> None:
    """An unreachable host is a connection error."""
    async with PreciosCarburantes(
        base_url="http://127.0.0.1:9", retry_delay=0
    ) as client:
        with pytest.raises(PreciosCarburantesConnectionError):
            await client.get_provinces()


async def test_api_error(aiohttp_server: ServerFactory) -> None:
    """A non-OK result is an API error."""
    client = await make_client(
        aiohttp_server,
        {
            "EstacionesTerrestres/FiltroMunicipio/1": lambda: web.json_response(
                {"ResultadoConsulta": "KO", "ListaEESSPrecio": []}
            )
        },
    )
    async with client:
        with pytest.raises(PreciosCarburantesError):
            await client.get_stations_by_municipality("1")


async def test_station_by_id(aiohttp_server: ServerFactory) -> None:
    """A restricted station is read from the Geoportal web."""
    client = await make_client(
        aiohttp_server,
        {
            "9683/busquedaEstacionPrecio": json_reply("geoportal_estacion.json"),
            "1/busquedaEstacionPrecio": lambda: web.Response(text=""),
        },
    )
    client._geoportal_url = client._base_url  # noqa: SLF001
    async with client:
        station = await client.get_station_by_id("9683")
        assert station.brand == "COOPERATIVA"
        assert station.sale_type is SaleType.RESTRICTED
        assert station.municipality_id is None
        assert station.latitude == pytest.approx(37.195583)
        assert station.prices == {
            FuelType.DIESEL_A: pytest.approx(1.802),
            FuelType.DIESEL_B: pytest.approx(1.477),
        }
        with pytest.raises(PreciosCarburantesNotFoundError):
            await client.get_station_by_id("1")


@pytest.mark.parametrize(
    ("path", "payload", "call"),
    [
        ("Listados/Provincias/", [{"Provincia": "X"}], "get_provinces"),
        (
            "EstacionesTerrestres/FiltroMunicipio/1",
            {"Fecha": "mal", "ListaEESSPrecio": []},
            "get_stations_by_municipality",
        ),
    ],
)
async def test_unexpected_format(
    aiohttp_server: ServerFactory, path: str, payload: Any, call: str
) -> None:
    """A changed response format is an API error, not a crash."""
    client = await make_client(
        aiohttp_server, {path: lambda: web.json_response(payload)}
    )
    async with client:
        method = getattr(client, call)
        with pytest.raises(PreciosCarburantesError):
            await (method() if call == "get_provinces" else method("1"))


async def test_retry_once(aiohttp_server: ServerFactory) -> None:
    """A single dropped request is retried; a second failure is raised."""
    calls = 0

    def flaky() -> web.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return web.Response(status=503)
        return web.json_response(load("provincias.json"))

    client = await make_client(aiohttp_server, {"Listados/Provincias/": flaky})
    async with client:
        assert len(await client.get_provinces()) == 3
        assert calls == 2

    calls = 0
    client = await make_client(
        aiohttp_server, {"Listados/Provincias/": lambda: web.Response(status=503)}
    )
    async with client:
        with pytest.raises(PreciosCarburantesConnectionError):
            await client.get_provinces()


async def test_no_retry_on_client_error(aiohttp_server: ServerFactory) -> None:
    """A 4xx answer is not retried."""
    calls = 0

    def not_found() -> web.Response:
        nonlocal calls
        calls += 1
        return web.Response(status=404)

    client = await make_client(aiohttp_server, {"Listados/Provincias/": not_found})
    async with client:
        with pytest.raises(PreciosCarburantesConnectionError):
            await client.get_provinces()
    assert calls == 1

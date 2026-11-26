"""Models for the Spanish fuel prices API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Europe/Madrid")


class FuelType(StrEnum):
    """Fuel types, keyed by the name used in the API (without "Precio ")."""

    ADBLUE = "Adblue"
    AMMONIA = "Amoniaco"
    BIODIESEL = "Biodiesel"
    BIOETHANOL = "Bioetanol"
    COMPRESSED_BIOGAS = "Biogas Natural Comprimido"
    LIQUEFIED_BIOGAS = "Biogas Natural Licuado"
    RENEWABLE_DIESEL = "Diésel Renovable"
    COMPRESSED_NATURAL_GAS = "Gas Natural Comprimido"
    LIQUEFIED_NATURAL_GAS = "Gas Natural Licuado"
    LPG = "Gases licuados del petróleo"
    DIESEL_A = "Gasoleo A"
    DIESEL_B = "Gasoleo B"
    DIESEL_PREMIUM = "Gasoleo Premium"
    GASOLINE_95_E10 = "Gasolina 95 E10"
    GASOLINE_95_E25 = "Gasolina 95 E25"
    GASOLINE_95_E5 = "Gasolina 95 E5"
    GASOLINE_95_E5_PREMIUM = "Gasolina 95 E5 Premium"
    GASOLINE_95_E85 = "Gasolina 95 E85"
    GASOLINE_98_E10 = "Gasolina 98 E10"
    GASOLINE_98_E5 = "Gasolina 98 E5"
    RENEWABLE_GASOLINE = "Gasolina Renovable"
    HYDROGEN = "Hidrogeno"
    METHANOL = "Metanol"


class SaleType(StrEnum):
    """Whether the station sells to the general public."""

    PUBLIC = "P"
    RESTRICTED = "R"


# Geoportal web codes for the sale type
GEOPORTAL_SALE_TYPES = {"C": SaleType.PUBLIC, "T": SaleType.RESTRICTED}

# Geoportal web price fields
GEOPORTAL_PRICE_FIELDS = {
    FuelType.ADBLUE: "precioAdb",
    FuelType.AMMONIA: "precioAmo",
    FuelType.BIODIESEL: "precioBiodiesel",
    FuelType.BIOETHANOL: "precioBioetanol",
    FuelType.COMPRESSED_BIOGAS: "precioBgnc",
    FuelType.LIQUEFIED_BIOGAS: "precioBgnl",
    FuelType.RENEWABLE_DIESEL: "precioDren",
    FuelType.COMPRESSED_NATURAL_GAS: "precioGasNatComp",
    FuelType.LIQUEFIED_NATURAL_GAS: "precioGasNatLicuado",
    FuelType.LPG: "precioGasesLicuados",
    FuelType.DIESEL_A: "precioGasoleoA",
    FuelType.DIESEL_B: "precioGasoleoB",
    FuelType.DIESEL_PREMIUM: "precioGasoleoPremium",
    FuelType.GASOLINE_95_E10: "precioGasolina95E10",
    FuelType.GASOLINE_95_E25: "precioGasolina95E25",
    FuelType.GASOLINE_95_E5: "precioGasolina95E5",
    FuelType.GASOLINE_95_E5_PREMIUM: "precioGasolina95E5Premium",
    FuelType.GASOLINE_95_E85: "precioGasolina95E85",
    FuelType.GASOLINE_98_E10: "precioGasolina98E10",
    FuelType.GASOLINE_98_E5: "precioGasolina98E5",
    FuelType.RENEWABLE_GASOLINE: "precioGren",
    FuelType.HYDROGEN: "precioHidrogeno",
    FuelType.METHANOL: "precioMet",
}


def parse_float(value: str | None) -> float | None:
    """Parse a number with a decimal comma; empty means no value."""
    if value is None or not value.strip():
        return None
    return float(value.replace(",", "."))


def parse_datetime(value: str) -> datetime:
    """Parse a "dd/mm/yyyy hh:mm:ss" timestamp in Spanish local time."""
    return datetime.strptime(value, "%d/%m/%Y %H:%M:%S").replace(tzinfo=TIMEZONE)


@dataclass(frozen=True, slots=True)
class Province:
    """A Spanish province."""

    id: str
    name: str
    autonomous_community_id: str
    autonomous_community: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Province:
        """Create from an API item (the API spells it "IDPovincia")."""
        return cls(
            id=data.get("IDPovincia") or data["IDProvincia"],
            name=data["Provincia"],
            autonomous_community_id=data["IDCCAA"],
            autonomous_community=data["CCAA"],
        )


@dataclass(frozen=True, slots=True)
class Municipality:
    """A Spanish municipality."""

    id: str
    name: str
    province_id: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Municipality:
        """Create from an API item."""
        return cls(
            id=data["IDMunicipio"],
            name=data["Municipio"],
            province_id=data["IDProvincia"],
        )


@dataclass(frozen=True, slots=True)
class Station:
    """A fuel station and its current prices in EUR per litre (or kg)."""

    id: str
    brand: str
    address: str
    locality: str
    municipality: str
    municipality_id: str | None
    province: str
    province_id: str | None
    postal_code: str
    schedule: str
    latitude: float | None
    longitude: float | None
    sale_type: SaleType
    prices: dict[FuelType, float] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Station:
        """Create from an API item, keeping only the fuels it sells."""
        prices: dict[FuelType, float] = {}
        for fuel in FuelType:
            price = parse_float(data.get(f"Precio {fuel.value}"))
            if price is not None:
                prices[fuel] = price
        return cls(
            id=data["IDEESS"],
            brand=data["Rótulo"],
            address=data["Dirección"],
            locality=data["Localidad"],
            municipality=data["Municipio"],
            municipality_id=data["IDMunicipio"],
            province=data["Provincia"],
            province_id=data["IDProvincia"],
            postal_code=data["C.P."],
            schedule=data["Horario"],
            latitude=parse_float(data.get("Latitud")),
            longitude=parse_float(data.get("Longitud (WGS84)")),
            sale_type=SaleType(data["Tipo Venta"]),
            prices=prices,
        )

    @classmethod
    def from_geoportal(cls, data: dict[str, Any]) -> Station:
        """Create from the Geoportal web, which has no municipality/province ids."""
        prices = {
            fuel: float(data[key])
            for fuel, key in GEOPORTAL_PRICE_FIELDS.items()
            if data.get(key) is not None
        }
        latitude = data.get("coordenadaY")
        longitude = data.get("coordenadaX")
        return cls(
            id=str(data["eessId"]),
            brand=data.get("rotulo") or "",
            address=data.get("direccion") or "",
            locality=data.get("localidad") or "",
            municipality=data.get("municipio") or "",
            municipality_id=None,
            province=data.get("provincia") or "",
            province_id=None,
            postal_code=data.get("codPostal") or "",
            schedule=data.get("horario") or "",
            latitude=None if latitude is None else float(latitude),
            longitude=None if longitude is None else float(longitude),
            sale_type=GEOPORTAL_SALE_TYPES.get(
                data.get("tipoVenta") or "", SaleType.RESTRICTED
            ),
            prices=prices,
        )


@dataclass(frozen=True, slots=True)
class StationList:
    """Stations returned by a query and when the prices were published."""

    updated_at: datetime
    stations: list[Station]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> StationList:
        """Create from an API response."""
        return cls(
            updated_at=parse_datetime(data["Fecha"]),
            stations=[Station.from_api(item) for item in data["ListaEESSPrecio"]],
        )

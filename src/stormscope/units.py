"""Unit conversion helpers for NWS observation data."""

from dataclasses import dataclass


_VALID_TEMPS = {"f", "c"}
_VALID_PRESSURES = {"inhg", "mb"}
_VALID_WINDS = {"mph", "kt", "kmh", "ms"}
_VALID_DISTANCES = {"mi", "km"}
_VALID_ACCUMULATIONS = {"in", "mm", "cm"}

_FIELD_VALIDATORS = {
    "temperature": _VALID_TEMPS,
    "pressure": _VALID_PRESSURES,
    "wind": _VALID_WINDS,
    "distance": _VALID_DISTANCES,
    "accumulation": _VALID_ACCUMULATIONS,
}


@dataclass(frozen=True)
class UnitPrefs:
    temperature: str  # "f" or "c"
    pressure: str     # "inhg" or "mb"
    wind: str         # "mph" or "kt" or "kmh" or "ms"
    distance: str     # "mi" or "km"
    accumulation: str  # "in" or "mm" or "cm"

    @classmethod
    def from_system(cls, system: str) -> "UnitPrefs":
        if system == "si":
            return cls(
                temperature="c", pressure="mb", wind="kmh",
                distance="km", accumulation="mm",
            )
        return cls(
            temperature="f", pressure="inhg", wind="mph",
            distance="mi", accumulation="in",
        )


def parse_units(raw: str | None, default_system: str = "us") -> UnitPrefs:
    """Parse 'us', 'si', or 'us,pressure:mb,wind:kt' into UnitPrefs."""
    if not raw:
        return UnitPrefs.from_system(default_system)

    parts = [p.strip() for p in raw.split(",")]
    base = parts[0].lower()
    if base not in ("us", "si"):
        raise ValueError(f"invalid unit system '{base}', must be 'us' or 'si'")

    prefs = UnitPrefs.from_system(base)
    overrides = {}
    for part in parts[1:]:
        if ":" not in part:
            raise ValueError(f"invalid unit override '{part}', expected 'field:value'")
        field, value = part.split(":", 1)
        field = field.strip().lower()
        value = value.strip().lower()
        if field not in _FIELD_VALIDATORS:
            raise ValueError(
                f"unknown unit field '{field}', must be one of: "
                f"{', '.join(sorted(_FIELD_VALIDATORS))}"
            )
        if value not in _FIELD_VALIDATORS[field]:
            raise ValueError(
                f"invalid value '{value}' for {field}, must be one of: "
                f"{', '.join(sorted(_FIELD_VALIDATORS[field]))}"
            )
        overrides[field] = value

    if overrides:
        from dataclasses import asdict
        d = asdict(prefs)
        d.update(overrides)
        prefs = UnitPrefs(**d)
    return prefs


def mm_to_inches(mm: float | None) -> float | None:
    """Convert millimeters to inches."""
    if mm is None:
        return None
    return mm / 25.4


def c_to_f(celsius: float | None) -> float | None:
    """Convert Celsius to Fahrenheit."""
    if celsius is None:
        return None
    return celsius * 9.0 / 5.0 + 32.0


def kmh_to_mph(kmh: float | None) -> float | None:
    """Convert km/h to mph."""
    if kmh is None:
        return None
    return kmh / 1.609344


def m_to_miles(meters: float | None) -> float | None:
    """Convert meters to miles."""
    if meters is None:
        return None
    return meters / 1609.344


def pa_to_inhg(pascals: float | None) -> float | None:
    """Convert Pascals to inches of mercury."""
    if pascals is None:
        return None
    return pascals / 3386.389


_CARDINALS = [
    "N", "NNE", "NE", "ENE",
    "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW",
    "W", "WNW", "NW", "NNW",
]


def ms_to_mph(ms: float | None) -> float | None:
    """Convert m/s to mph."""
    if ms is None:
        return None
    return ms * 2.236936


def m_to_ft(meters: float | None) -> float | None:
    """Convert meters to feet."""
    if meters is None:
        return None
    return meters * 3.28084


def pa_to_hpa(pascals: float | None) -> float | None:
    """Convert Pascals to hectopascals (millibars)."""
    if pascals is None:
        return None
    return pascals / 100.0


def degrees_to_cardinal(degrees: float | None) -> str | None:
    """Convert compass degrees to 16-point cardinal direction."""
    if degrees is None:
        return None
    idx = round(degrees / 22.5) % 16
    return _CARDINALS[idx]


def ms_to_kt(ms: float | None) -> float | None:
    """Convert m/s to knots."""
    if ms is None:
        return None
    return ms * 1.94384


def gpm_to_dam(gpm: float | None) -> float | None:
    """Convert geopotential meters to decameters."""
    if gpm is None:
        return None
    return gpm / 10.0

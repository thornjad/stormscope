"""Unit conversion helpers for NWS observation data."""


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

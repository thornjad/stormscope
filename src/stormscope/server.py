"""stormscope MCP server."""

from contextlib import asynccontextmanager

from fastmcp import FastMCP

from stormscope import tools
from stormscope.config import config
from stormscope.geo import geolocate
from stormscope.units import parse_units

_tempest_station_location: tuple[float, float] | None = None
_tempest_station_location_fetched = False


@asynccontextmanager
async def _lifespan(app):
    yield
    await tools.shutdown()


mcp = FastMCP(
    "stormscope",
    lifespan=_lifespan,
    instructions=(
        "You have access to real-time US weather data via the StormScope tools. "
        "At the start of each conversation, if a primary location is configured, "
        "check for active weather alerts using get_alerts. If any of the following "
        "are active, immediately notify the user:\n"
        "- Tornado Warning (take shelter immediately)\n"
        "- Severe Thunderstorm Warning (damaging winds/hail possible)\n"
        "- Flash Flood Warning or Flash Flood Emergency (avoid flood areas)\n"
        "- Extreme Wind Warning\n"
        "- Tsunami Warning\n"
        "- TORNADO EMERGENCY (catastrophic, life-threatening situation)\n\n"
        "For PDS (Particularly Dangerous Situation) watches, emphasize the "
        "elevated threat level. For other alerts (watches, advisories), mention "
        "them when contextually relevant but do not interrupt the user's workflow.\n\n"
        "When the SPC outlook shows ENH or higher risk, proactively fetch "
        "probabilistic tornado/wind/hail outlooks and the national outlook to "
        "provide full context. When MDT or HIGH risk is present nationally, "
        "mention it even if the user's location is not directly affected.\n\n"
        "Use get_briefing for general weather requests. Use specific tools "
        "(get_conditions, get_forecast, get_alerts, get_spc_outlook, get_radar) "
        "when the user asks for targeted data.\n\n"
        "Use get_upper_air when the user asks about 500mb analysis, upper-air "
        "patterns, troughs, ridges, jet stream, vorticity, or shortwave features. "
        "This tool uses global model data and is not limited to US locations.\n\n"
        "Use get_surface_analysis when the user asks about fronts, warm/cold "
        "sectors, surface lows/highs, or synoptic surface patterns. Returns "
        "distance and bearing to nearby fronts and pressure centers, plus "
        "warm/cold sector detection relative to the nearest cold front.\n\n"
        "When a Tempest weather station is configured, get_conditions includes "
        "hyper-local sensor data from the user's personal station: solar_radiation, "
        "uv_index, lightning_strikes_1hr, air_density, and wet_bulb_temperature. "
        "The data_source field indicates whether primary readings (temperature, "
        "wind, pressure) come from the Tempest station or NWS. Forecasts include "
        "sunrise and sunset times, and supplementary Tempest high/low temperatures "
        "when available."
    ),
)


_VALID_DETAILS = {"standard", "full"}

def _validate_units(units: str | None) -> dict | None:
    """validate units string, return error dict if invalid."""
    if units is None:
        return None
    try:
        parse_units(units, config.units)
        return None
    except ValueError as exc:
        return {"error": str(exc)}


async def _get_tempest_station_location() -> tuple[float, float] | None:
    """return cached tempest station coords, resolving once on first call."""
    global _tempest_station_location, _tempest_station_location_fetched
    if _tempest_station_location_fetched:
        return _tempest_station_location
    _tempest_station_location_fetched = True
    coords = await tools.get_tempest_station_location()
    _tempest_station_location = coords
    return coords


async def _resolve_location(
    latitude: float | None, longitude: float | None,
) -> tuple[float, float]:
    # explicit params always win
    if latitude is not None and longitude is not None:
        if not (-90 <= latitude <= 90):
            raise ValueError(f"latitude {latitude} out of range, must be -90 to 90")
        if not (-180 <= longitude <= 180):
            raise ValueError(f"longitude {longitude} out of range, must be -180 to 180")
        return latitude, longitude

    # tempest station location override
    if config.tempest_enabled and config.use_tempest_station_geolocation:
        coords = await _get_tempest_station_location()
        if coords is not None:
            return coords

    lat = latitude if latitude is not None else config.primary_latitude
    lon = longitude if longitude is not None else config.primary_longitude
    if lat is not None and lon is not None:
        if not (-90 <= lat <= 90):
            raise ValueError(f"latitude {lat} out of range, must be -90 to 90")
        if not (-180 <= lon <= 180):
            raise ValueError(f"longitude {lon} out of range, must be -180 to 180")
        return lat, lon
    coords = await geolocate(
        disabled=config.disable_auto_geolocation,
        enable_corelocation=config.enable_corelocation,
    )
    if coords is not None:
        return coords
    raise ValueError(
        "no location provided and no primary location configured. "
        "Set PRIMARY_LATITUDE and PRIMARY_LONGITUDE environment variables "
        "or pass latitude and longitude explicitly."
    )


@mcp.tool()
async def get_conditions(
    latitude: float | None = None,
    longitude: float | None = None,
    detail: str = "standard",
    units: str | None = None,
) -> dict:
    """Get current weather conditions for a US location.

    Use when: "What's the weather right now?", "How hot is it?", "Is it windy?"

    detail="standard": temperature, feels-like, dewpoint (or frost_point when <= 0C),
    humidity, wind, sky, visibility, pressure.
    detail="full": adds cloud layers, present weather, raw METAR.

    Omit lat/lon to use configured primary location.

    units: "us" or "si" for base system, with optional field overrides:
    "us,pressure:mb,wind:kt". Fields: temperature (f|c), pressure (inhg|mb),
    wind (mph|kt|kmh|ms), distance (mi|km), accumulation (in|mm|cm).
    """
    if detail not in _VALID_DETAILS:
        return {"error": f"invalid detail '{detail}', must be one of: standard, full"}
    err = _validate_units(units)
    if err:
        return err
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_conditions(lat, lon, detail, units=units)


@mcp.tool()
async def get_forecast(
    latitude: float | None = None,
    longitude: float | None = None,
    mode: str = "daily",
    days: int = 7,
    hours: int = 24,
    units: str | None = None,
) -> dict:
    """Get forecast for a US location.

    Use when: "What's the forecast?", "Will it rain?", "Weather this week?"

    mode="daily": 12-hour day/night periods with narrative forecasts (default).
    mode="hourly": hour-by-hour temperature, precip chance, wind.
    mode="raw": gridpoint time-value series for temperature, dewpoint, wind, precip, sky cover.

    days (1-7) controls daily mode. hours (1-48) controls hourly mode.
    Omit lat/lon to use configured primary location.

    Note: the main temperature and wind fields in daily/hourly periods come from
    NWS pre-formatted data and are always in Fahrenheit/mph. The units parameter
    affects enriched fields: dewpoint/frost_point, feels_like, pressure, and
    snow/ice accumulation. Use mode="raw" for full unit-agnostic gridpoint data.

    units: "us" or "si" for base system, with optional field overrides:
    "us,pressure:mb,wind:kt". Fields: temperature (f|c), pressure (inhg|mb),
    wind (mph|kt|kmh|ms), distance (mi|km), accumulation (in|mm|cm).
    """
    err = _validate_units(units)
    if err:
        return err
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    if not (1 <= days <= 7):
        return {"error": f"invalid days {days}, must be 1-7"}
    if not (1 <= hours <= 48):
        return {"error": f"invalid hours {hours}, must be 1-48"}
    return await tools.get_forecast(lat, lon, mode, days, hours, units=units)


@mcp.tool()
async def get_alerts(
    latitude: float | None = None,
    longitude: float | None = None,
    severity_filter: str | None = None,
    detail: str = "standard",
    units: str | None = None,
) -> dict:
    """Get active weather alerts for a US location.

    Use proactively at conversation start. Also: "Any warnings?", "Is it safe to travel?"

    severity_filter: "Extreme", "Severe", "Moderate", or "Minor" to filter.
    detail="standard": event, severity, headline, description, instructions.
    detail="full": adds VTEC codes, polygon geometry, areaDesc, sender.

    Omit lat/lon to use configured primary location.

    units: accepted for API consistency but does not affect alert output.
    Alert text is returned as-is from NWS.
    """
    if detail not in _VALID_DETAILS:
        return {"error": f"invalid detail '{detail}', must be one of: standard, full"}
    err = _validate_units(units)
    if err:
        return err
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_alerts(lat, lon, severity_filter, detail, units=units)


@mcp.tool()
async def get_spc_outlook(
    latitude: float | None = None,
    longitude: float | None = None,
    outlook_type: str = "categorical",
    day: int = 1,
    units: str | None = None,
) -> dict:
    """Check SPC severe weather outlook for a US location.

    Use when: "Severe weather risk?", "Storm outlook?", "Should I worry about storms?"

    outlook_type="categorical": risk level (NONE/TSTM/MRGL/SLGT/ENH/MDT/HIGH).
    outlook_type="tornado"/"wind"/"hail": probabilistic hazard percentage + significant flag.

    day: 1=today, 2=tomorrow, 3=day after.
    Omit lat/lon to use configured primary location.

    units: accepted for API consistency but does not affect SPC outlook output.
    Risk levels and probabilities are unitless.
    """
    err = _validate_units(units)
    if err:
        return err
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_spc_outlook(lat, lon, outlook_type, day, units=units)


@mcp.tool()
async def get_national_outlook(day: int = 1, units: str | None = None) -> dict:
    """Get CONUS-wide SPC severe weather risk areas.

    Use when: "Any severe weather in the US?", "National storm outlook?"

    Returns all active risk areas with human-readable region descriptions
    (e.g. "central Oklahoma", "northern Texas"). No lat/lon needed.

    day: 1=today, 2=tomorrow, 3=day after.

    units: accepted for API consistency but does not affect outlook output.
    Risk levels and region descriptions are unitless.
    """
    err = _validate_units(units)
    if err:
        return err
    return await tools.get_national_outlook(day, units=units)


@mcp.tool()
async def get_radar(
    latitude: float | None = None,
    longitude: float | None = None,
    units: str | None = None,
) -> dict:
    """Get NEXRAD radar info with textual weather summary and clickable links.

    Use when: "Show me radar", "What does radar look like?", "Radar imagery?"

    Returns a textual summary of current precipitation and near-term outlook
    (useful when images can't be displayed), plus clickable links to radar
    imagery the user can open in a browser. Also includes station ID, available
    products, and latest scan time.

    Omit lat/lon to use configured primary location.

    units: accepted for API consistency but does not affect radar output.
    Radar data is imagery-based and unitless.
    """
    err = _validate_units(units)
    if err:
        return err
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_radar(lat, lon, units=units)


@mcp.tool()
async def get_briefing(
    latitude: float | None = None,
    longitude: float | None = None,
    detail: str = "standard",
    units: str | None = None,
) -> dict:
    """Get a comprehensive weather briefing for a US location.

    The default tool for "What's the weather?" — combines conditions, forecast,
    alerts, and SPC outlook.

    detail="standard": current conditions + today/tonight forecast + alerts + categorical SPC.
    detail="full": adds probabilistic outlooks (when MRGL+), national outlook,
    radar, and day 2-3 SPC forecasts.

    Omit lat/lon to use configured primary location.

    units: "us" or "si" for base system, with optional field overrides:
    "us,pressure:mb,wind:kt". Fields: temperature (f|c), pressure (inhg|mb),
    wind (mph|kt|kmh|ms), distance (mi|km), accumulation (in|mm|cm).
    """
    if detail not in _VALID_DETAILS:
        return {"error": f"invalid detail '{detail}', must be one of: standard, full"}
    err = _validate_units(units)
    if err:
        return err
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_briefing(lat, lon, detail, units=units)


@mcp.tool()
async def get_upper_air(
    latitude: float | None = None,
    longitude: float | None = None,
    units: str | None = None,
) -> dict:
    """Get 500mb upper-air analysis with heights, temperature, wind, and vorticity.

    Use when: "What does 500mb look like?", "Where are the troughs?",
    "Upper-air pattern?", "Jet stream?", "Vorticity?"

    500mb (~18,000 ft) is the key level for synoptic-scale analysis:
    - Heights reveal troughs (low heights, stormier) and ridges (high heights, calmer)
    - Vorticity maxima indicate regions favorable for storm development
    - Wind shows the jet stream position and strength

    Returns 12-hour time series with height (dam), temperature, wind, and
    derived relative/absolute vorticity (10^-5 s^-1) from a 5-point
    finite-difference grid at ~110km spacing.

    Not US-only — uses global GFS model data via Open-Meteo.
    Omit lat/lon to use configured primary location.

    units: "us" or "si" for base system, with optional field overrides:
    "us,pressure:mb,wind:kt". Fields: temperature (f|c), pressure (inhg|mb),
    wind (mph|kt|kmh|ms), distance (mi|km), accumulation (in|mm|cm).
    """
    err = _validate_units(units)
    if err:
        return err
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_upper_air(lat, lon, units=units)


@mcp.tool()
async def get_surface_analysis(
    latitude: float | None = None,
    longitude: float | None = None,
    product: str = "analysis",
    day: int = 0,
    detail: str = "standard",
    scope: str = "local",
    units: str | None = None,
) -> dict:
    """Get surface analysis or forecast showing fronts, pressure centers, and warm/cold sector.

    Use when: "Where are the fronts?", "Am I in the warm sector?",
    "Surface analysis?", "Where's the nearest low?"

    Returns distance and bearing from your location to nearby fronts and
    pressure centers (highs/lows). For cold fronts, determines whether
    you're on the warm side (ahead) or cold side (behind).

    product="analysis" (default): WPC coded surface analysis (CODSUS) showing
    current front positions and pressure centers, updated every 3 hours.
    Includes pressure values on H/L centers. The day parameter is not used.
    product="forecast": WPC national forecast chart. day: 1=today, 2=tomorrow,
    3=day after.

    detail="standard": nearest ~5 fronts, ~4 pressure centers, location summary.
    detail="full": all features with nearest-point coordinates.

    scope="local" (default): location summary only references fronts within
    ~400km — distant fronts are listed but not described as influencing
    local weather. Use for typical queries about local conditions.
    scope="all": no distance threshold — location summary always reports
    warm/cold sector relative to nearest cold front regardless of distance.
    Use when asking about the broad synoptic pattern.

    Note: this tool reports synoptic-scale features (major fronts, pressure
    centers). Mesoscale boundaries such as outflow boundaries, sea breezes,
    and moisture gradients are not included in the CODSUS or forecast chart
    data sources.

    Warm/cold sector detection is approximate (geometric heuristic). CONUS
    coverage only.

    Omit lat/lon to use configured primary location.

    units: "us" or "si" for base system, with optional field overrides:
    "us,pressure:mb,wind:kt". Fields: temperature (f|c), pressure (inhg|mb),
    wind (mph|kt|kmh|ms), distance (mi|km), accumulation (in|mm|cm).
    """
    if product not in ("analysis", "forecast"):
        return {"error": f"invalid product '{product}', must be 'analysis' or 'forecast'"}
    if detail not in _VALID_DETAILS:
        return {"error": f"invalid detail '{detail}', must be one of: standard, full"}
    if scope not in ("local", "all"):
        return {"error": f"invalid scope '{scope}', must be 'local' or 'all'"}
    err = _validate_units(units)
    if err:
        return err
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_surface_analysis(
        lat, lon, product=product, day=day, detail=detail, units=units, scope=scope,
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()

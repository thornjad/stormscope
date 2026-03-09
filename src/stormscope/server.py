"""stormscope MCP server."""

from contextlib import asynccontextmanager

from fastmcp import FastMCP

from stormscope import tools
from stormscope.config import config
from stormscope.geo import geolocate


@asynccontextmanager
async def _lifespan(app):
    yield
    await tools.shutdown()


mcp = FastMCP(
    "stormscope",
    lifespan=_lifespan,
    instructions=(
        "You have access to real-time US weather data via the stormscope tools. "
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
        "warm/cold sector detection relative to the nearest cold front."
    ),
)


_VALID_DETAILS = {"standard", "full"}


async def _resolve_location(
    latitude: float | None, longitude: float | None,
) -> tuple[float, float]:
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
) -> dict:
    """Get current weather conditions for a US location.

    Use when: "What's the weather right now?", "How hot is it?", "Is it windy?"

    detail="standard": temperature, feels-like, humidity, wind, sky, visibility, pressure.
    detail="full": adds dewpoint, cloud layers, present weather, raw METAR.

    Omit lat/lon to use configured primary location.
    """
    if detail not in _VALID_DETAILS:
        return {"error": f"invalid detail '{detail}', must be one of: standard, full"}
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_conditions(lat, lon, detail)


@mcp.tool()
async def get_forecast(
    latitude: float | None = None,
    longitude: float | None = None,
    mode: str = "daily",
    days: int = 7,
    hours: int = 24,
) -> dict:
    """Get forecast for a US location.

    Use when: "What's the forecast?", "Will it rain?", "Weather this week?"

    mode="daily": 12-hour day/night periods with narrative forecasts (default).
    mode="hourly": hour-by-hour temperature, precip chance, wind.
    mode="raw": gridpoint time-value series for temperature, dewpoint, wind, precip, sky cover.

    days (1-7) controls daily mode. hours (1-48) controls hourly mode.
    Omit lat/lon to use configured primary location.
    """
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    if not (1 <= days <= 7):
        return {"error": f"invalid days {days}, must be 1-7"}
    if not (1 <= hours <= 48):
        return {"error": f"invalid hours {hours}, must be 1-48"}
    return await tools.get_forecast(lat, lon, mode, days, hours)


@mcp.tool()
async def get_alerts(
    latitude: float | None = None,
    longitude: float | None = None,
    severity_filter: str | None = None,
    detail: str = "standard",
) -> dict:
    """Get active weather alerts for a US location.

    Use proactively at conversation start. Also: "Any warnings?", "Is it safe to travel?"

    severity_filter: "Extreme", "Severe", "Moderate", or "Minor" to filter.
    detail="standard": event, severity, headline, description, instructions.
    detail="full": adds VTEC codes, polygon geometry, areaDesc, sender.

    Omit lat/lon to use configured primary location.
    """
    if detail not in _VALID_DETAILS:
        return {"error": f"invalid detail '{detail}', must be one of: standard, full"}
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_alerts(lat, lon, severity_filter, detail)


@mcp.tool()
async def get_spc_outlook(
    latitude: float | None = None,
    longitude: float | None = None,
    outlook_type: str = "categorical",
    day: int = 1,
) -> dict:
    """Check SPC severe weather outlook for a US location.

    Use when: "Severe weather risk?", "Storm outlook?", "Should I worry about storms?"

    outlook_type="categorical": risk level (NONE/TSTM/MRGL/SLGT/ENH/MDT/HIGH).
    outlook_type="tornado"/"wind"/"hail": probabilistic hazard percentage + significant flag.

    day: 1=today, 2=tomorrow, 3=day after.
    Omit lat/lon to use configured primary location.
    """
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_spc_outlook(lat, lon, outlook_type, day)


@mcp.tool()
async def get_national_outlook(day: int = 1) -> dict:
    """Get CONUS-wide SPC severe weather risk areas.

    Use when: "Any severe weather in the US?", "National storm outlook?"

    Returns all active risk areas with human-readable region descriptions
    (e.g. "central Oklahoma", "northern Texas"). No lat/lon needed.

    day: 1=today, 2=tomorrow, 3=day after.
    """
    return await tools.get_national_outlook(day)


@mcp.tool()
async def get_radar(
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict:
    """Get NEXRAD radar info with textual weather summary and clickable links.

    Use when: "Show me radar", "What does radar look like?", "Radar imagery?"

    Returns a textual summary of current precipitation and near-term outlook
    (useful when images can't be displayed), plus clickable links to radar
    imagery the user can open in a browser. Also includes station ID, available
    products, and latest scan time.

    Omit lat/lon to use configured primary location.
    """
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_radar(lat, lon)


@mcp.tool()
async def get_briefing(
    latitude: float | None = None,
    longitude: float | None = None,
    detail: str = "standard",
) -> dict:
    """Get a comprehensive weather briefing for a US location.

    The default tool for "What's the weather?" — combines conditions, forecast,
    alerts, and SPC outlook.

    detail="standard": current conditions + today/tonight forecast + alerts + categorical SPC.
    detail="full": adds probabilistic outlooks (when MRGL+), national outlook,
    radar, and day 2-3 SPC forecasts.

    Omit lat/lon to use configured primary location.
    """
    if detail not in _VALID_DETAILS:
        return {"error": f"invalid detail '{detail}', must be one of: standard, full"}
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_briefing(lat, lon, detail)


@mcp.tool()
async def get_upper_air(
    latitude: float | None = None,
    longitude: float | None = None,
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
    """
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_upper_air(lat, lon)


@mcp.tool()
async def get_surface_analysis(
    latitude: float | None = None,
    longitude: float | None = None,
    day: int = 1,
    detail: str = "standard",
) -> dict:
    """Get WPC surface analysis showing fronts, pressure centers, and warm/cold sector.

    Use when: "Where are the fronts?", "Am I in the warm sector?",
    "Surface analysis?", "Where's the nearest low?"

    Returns distance and bearing from your location to nearby fronts and
    pressure centers (highs/lows). For cold fronts, determines whether
    you're on the warm side (ahead) or cold side (behind).

    day: 1=today, 2=tomorrow, 3=day after.
    detail="standard": nearest ~5 fronts, ~4 pressure centers, location summary.
    detail="full": all features with nearest-point coordinates.

    Limitations: no pressure values on H/L centers, warm/cold sector detection
    is approximate (geometric heuristic), CONUS coverage, analysis charts
    updated ~4x/day.

    Omit lat/lon to use configured primary location.
    """
    if detail not in _VALID_DETAILS:
        return {"error": f"invalid detail '{detail}', must be one of: standard, full"}
    try:
        lat, lon = await _resolve_location(latitude, longitude)
    except ValueError as exc:
        return {"error": str(exc)}
    return await tools.get_surface_analysis(lat, lon, day, detail)


def main():
    mcp.run()


if __name__ == "__main__":
    main()

"""Weather tool functions for the MCP server."""

import asyncio
import logging
import math
from datetime import datetime

from stormscope.config import config
from stormscope.iem import IEMClient
from stormscope.nws import NWSClient
from stormscope.openmeteo import OpenMeteoClient
from stormscope.spc import SPCClient
from stormscope.units import (
    UnitPrefs, c_to_f, degrees_to_cardinal, gpm_to_dam, kmh_to_mph,
    m_to_miles, mm_to_inches, ms_to_kt, ms_to_mph, pa_to_inhg,
    parse_units,
)
from stormscope.vorticity import compute_vorticity
from stormscope.wpc import WPCClient, FRONT_TYPES, CENTER_TYPES

logger = logging.getLogger(__name__)

_nws = NWSClient()
_spc = SPCClient()
_iem = IEMClient()
_openmeteo = OpenMeteoClient()
_wpc = WPCClient()


async def shutdown():
    """close all HTTP clients."""
    await _nws.close()
    await _spc.close()
    await _iem.close()
    await _openmeteo.close()
    await _wpc.close()


def _obs_value(obs: dict, field: str) -> float | None:
    entry = obs.get(field)
    if entry is None:
        return None
    return entry.get("value")


def _fmt_temp(fahrenheit: float | None, celsius: float | None, prefs: UnitPrefs) -> str:
    if prefs.temperature == "c":
        if celsius is None:
            return "N/A"
        return f"{round(celsius)}°C"
    if fahrenheit is None:
        return "N/A"
    return f"{round(fahrenheit)}°F"


_WIND_UNITS = {"mph": "mph", "kt": "kt", "kmh": "km/h", "ms": "m/s"}


def _convert_obs_wind(kmh: float | None, prefs: UnitPrefs) -> float | None:
    """convert observation wind from km/h to the preferred unit."""
    if kmh is None:
        return None
    if prefs.wind == "kmh":
        return kmh
    if prefs.wind == "mph":
        return kmh_to_mph(kmh)
    if prefs.wind == "kt":
        return ms_to_kt(kmh / 3.6)
    # m/s
    return kmh / 3.6


def _fmt_wind(speed: float | None, direction: str | None, prefs: UnitPrefs) -> str:
    if speed is None:
        return "Calm"
    s = round(speed)
    if s == 0:
        return "Calm"
    unit = _WIND_UNITS[prefs.wind]
    if direction:
        return f"{direction} {s} {unit}"
    return f"{s} {unit}"


def _fmt_humidity(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{round(value)}%"


def _fmt_visibility(miles: float | None, meters: float | None, prefs: UnitPrefs) -> str:
    if prefs.distance == "km":
        if meters is None:
            return "N/A"
        km = meters / 1000
        return f"{km:.1f} km"
    if miles is None:
        return "N/A"
    return f"{miles:.1f} mi"


def _fmt_pressure(inhg: float | None, pascals: float | None, prefs: UnitPrefs) -> str:
    if prefs.pressure == "mb":
        if pascals is None:
            return "N/A"
        hpa = pascals / 100
        return f"{hpa:.1f} mb"
    if inhg is None:
        return "N/A"
    return f"{inhg:.2f} inHg"


def _fmt_gust(speed: float | None, prefs: UnitPrefs) -> str:
    if speed is None:
        return "calm"
    unit = _WIND_UNITS[prefs.wind]
    return f"{round(speed)} {unit}"


def _fmt_accumulation(mm: float | None, prefs: UnitPrefs) -> str:
    if mm is None or mm == 0:
        return "0"
    if prefs.accumulation == "in":
        inches = mm_to_inches(mm)
        return f"{inches:.2f} in"
    if prefs.accumulation == "cm":
        return f"{mm / 10:.1f} cm"
    return f"{mm:.1f} mm"


def _location_name(point: dict) -> str:
    rel = point.get("relativeLocation", {}).get("properties", {})
    city = rel.get("city", "Unknown")
    state = rel.get("state", "")
    if state:
        return f"{city}, {state}"
    return city


def _grid_values_for_periods(
    grid_field: dict, periods: list[dict], aggregate: str = "avg",
) -> list[float | None]:
    """extract aggregated values per forecast period from gridpoint time series.

    aggregate="avg" averages values in the period (temperature, pressure, dewpoint).
    aggregate="sum" sums values (snowfall, ice accumulation).
    returns raw floats; callers format with the appropriate _fmt_* function.
    """
    values = grid_field.get("values", [])
    if not values:
        return [None] * len(periods)

    parsed = []
    for v in values:
        try:
            vtime = datetime.fromisoformat(v["validTime"].split("/")[0])
            if v["value"] is not None:
                parsed.append((vtime, v["value"]))
        except (KeyError, ValueError):
            continue

    if not parsed:
        return [None] * len(periods)

    result = []
    for period in periods:
        try:
            start = datetime.fromisoformat(period["startTime"])
            end_str = period.get("endTime")
            if end_str:
                end = datetime.fromisoformat(end_str)
                matching = [c for t, c in parsed if start <= t < end]
            else:
                closest = min(parsed, key=lambda p: abs((p[0] - start).total_seconds()))
                matching = [closest[1]]

            if matching:
                if aggregate == "sum":
                    result.append(sum(matching))
                else:
                    result.append(sum(matching) / len(matching))
            else:
                result.append(None)
        except (KeyError, ValueError):
            result.append(None)
    return result


_SEVERITY_ORDER = {
    "Extreme": 0,
    "Severe": 1,
    "Moderate": 2,
    "Minor": 3,
    "Unknown": 4,
}


async def get_conditions(
    latitude: float, longitude: float, detail: str = "standard",
    units: str | None = None,
) -> dict:
    """Get current weather conditions."""
    prefs = parse_units(units, config.units)
    try:
        point = await _nws.get_point(latitude, longitude)
        stations = await _nws.get_stations(point["observationStations"])
        if not stations:
            return {"error": "no observation stations found near this location"}

        station = stations[0]
        obs = await _nws.get_latest_observation(station["stationIdentifier"])

        temp_c = _obs_value(obs, "temperature")
        wind_chill_c = _obs_value(obs, "windChill")
        heat_index_c = _obs_value(obs, "heatIndex")
        wind_kmh = _obs_value(obs, "windSpeed")
        wind_deg = _obs_value(obs, "windDirection")
        gust_kmh = _obs_value(obs, "windGust")
        humidity = _obs_value(obs, "relativeHumidity")
        vis_m = _obs_value(obs, "visibility")
        pressure_pa = _obs_value(obs, "barometricPressure")

        temp_f = c_to_f(temp_c)
        feels_like_c = heat_index_c if heat_index_c is not None else wind_chill_c
        fl = c_to_f(feels_like_c)
        feels_like_f = fl if fl is not None else temp_f

        dewpoint_c = _obs_value(obs, "dewpoint")
        dewpoint_f = c_to_f(dewpoint_c)
        wind_speed = _convert_obs_wind(wind_kmh, prefs)
        gust_speed = _convert_obs_wind(gust_kmh, prefs)
        cardinal = degrees_to_cardinal(wind_deg)

        # frost point vs dewpoint labeling
        dp_key = "frost_point" if dewpoint_c is not None and dewpoint_c < 0 else "dewpoint"

        result = {
            "temperature": _fmt_temp(temp_f, temp_c, prefs),
            "feels_like": _fmt_temp(feels_like_f, feels_like_c if feels_like_c is not None else temp_c, prefs),
            dp_key: _fmt_temp(dewpoint_f, dewpoint_c, prefs),
            "humidity": _fmt_humidity(humidity),
            "wind": _fmt_wind(wind_speed, cardinal, prefs),
            "wind_gust": _fmt_gust(gust_speed, prefs),
            "sky_condition": obs.get("textDescription", "N/A"),
            "visibility": _fmt_visibility(m_to_miles(vis_m), vis_m, prefs),
            "pressure": _fmt_pressure(pa_to_inhg(pressure_pa), pressure_pa, prefs),
            "station_name": station.get("name", "Unknown"),
            "observation_time": obs.get("timestamp", "N/A"),
        }

        if detail == "full":
            result["cloud_layers"] = obs.get("cloudLayers", [])
            result["present_weather"] = obs.get("presentWeather", [])
            result["wind_direction"] = cardinal or "N/A"
            result["raw_observation"] = obs.get("rawMessage", "")

        return result
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        logger.exception("error fetching current conditions")
        return {"error": f"failed to fetch conditions: {exc}"}


_VALID_MODES = {"daily", "hourly", "raw"}


def _extract_grid_arrays(grid_data: dict, periods: list[dict]) -> dict:
    """precompute all enriched grid field arrays once for the period list."""
    n = len(periods)
    if not grid_data:
        return {k: [None] * n for k in (
            "dewpoint", "apparentTemperature", "pressure",
            "snowfallAmount", "iceAccumulation",
        )}
    return {
        "dewpoint": _grid_values_for_periods(grid_data.get("dewpoint", {}), periods),
        "apparentTemperature": _grid_values_for_periods(grid_data.get("apparentTemperature", {}), periods),
        "pressure": _grid_values_for_periods(grid_data.get("pressure", {}), periods),
        "snowfallAmount": _grid_values_for_periods(grid_data.get("snowfallAmount", {}), periods, aggregate="sum"),
        "iceAccumulation": _grid_values_for_periods(grid_data.get("iceAccumulation", {}), periods, aggregate="sum"),
    }


def _build_forecast_period(
    period: dict, i: int, grid_arrays: dict, prefs: UnitPrefs,
    include_daily_fields: bool = False,
) -> dict:
    """build a single forecast period dict with enriched grid fields."""
    entry: dict = {}
    if include_daily_fields:
        entry["name"] = period["name"]

    entry["temperature"] = f"{period['temperature']}°{period['temperatureUnit']}"

    if not include_daily_fields:
        entry["start_time"] = period["startTime"]

    # dewpoint / frost point
    dp_c = grid_arrays["dewpoint"][i] if i < len(grid_arrays["dewpoint"]) else None
    dp_key = "frost_point" if dp_c is not None and dp_c < 0 else "dewpoint"
    entry[dp_key] = _fmt_temp(c_to_f(dp_c), dp_c, prefs) if dp_c is not None else "N/A"

    # feels like (apparent temperature)
    at_c = grid_arrays["apparentTemperature"][i] if i < len(grid_arrays["apparentTemperature"]) else None
    entry["feels_like"] = _fmt_temp(c_to_f(at_c), at_c, prefs) if at_c is not None else "N/A"

    # pressure
    pa = grid_arrays["pressure"][i] if i < len(grid_arrays["pressure"]) else None
    entry["pressure"] = _fmt_pressure(pa_to_inhg(pa), pa, prefs) if pa is not None else "N/A"

    entry["wind"] = f"{period['windDirection']} {period['windSpeed']}"
    entry["forecast"] = period["shortForecast"]

    if include_daily_fields:
        entry["detailed"] = period["detailedForecast"]
        entry["is_daytime"] = period["isDaytime"]

    if not include_daily_fields:
        entry["precipitation_chance"] = f"{period.get('probabilityOfPrecipitation', {}).get('value', 0) or 0}%"

    # snow accumulation
    snow_mm = grid_arrays["snowfallAmount"][i] if i < len(grid_arrays["snowfallAmount"]) else None
    if snow_mm and snow_mm > 0:
        entry["snow_accumulation"] = _fmt_accumulation(snow_mm, prefs)

    # ice accumulation
    ice_mm = grid_arrays["iceAccumulation"][i] if i < len(grid_arrays["iceAccumulation"]) else None
    if ice_mm and ice_mm > 0:
        entry["ice_accumulation"] = _fmt_accumulation(ice_mm, prefs)

    return entry


async def get_forecast(
    latitude: float, longitude: float,
    mode: str = "daily", days: int = 7, hours: int = 24,
    units: str | None = None,
) -> dict:
    """Get forecast: daily (12h periods), hourly, or raw gridpoint data."""
    if mode not in _VALID_MODES:
        return {"error": f"invalid mode '{mode}', must be one of: daily, hourly, raw"}
    prefs = parse_units(units, config.units)
    try:
        point = await _nws.get_point(latitude, longitude)
        wfo, x, y = point["gridId"], point["gridX"], point["gridY"]

        if mode == "hourly":
            hourly_data, grid_data = await asyncio.gather(
                _nws.get_hourly_forecast(wfo, x, y),
                _nws.get_detailed_forecast(wfo, x, y),
                return_exceptions=True,
            )
            if isinstance(hourly_data, Exception):
                raise hourly_data
            periods = hourly_data.get("periods", [])[:hours]
            gd = grid_data if not isinstance(grid_data, Exception) else {}
            if isinstance(grid_data, Exception):
                logger.debug("grid data fetch failed, enriched fields unavailable: %s", grid_data)
            arrays = _extract_grid_arrays(gd, periods)
            return {
                "location": _location_name(point),
                "periods": [
                    _build_forecast_period(p, i, arrays, prefs)
                    for i, p in enumerate(periods)
                ],
            }

        if mode == "raw":
            data = await _nws.get_detailed_forecast(wfo, x, y)
            params = [
                "temperature", "dewpoint", "windSpeed", "windDirection",
                "probabilityOfPrecipitation", "skyCover", "weather",
                "apparentTemperature", "pressure", "snowfallAmount",
                "iceAccumulation",
            ]
            return {
                "location": _location_name(point),
                "grid": {k: data.get(k) for k in params if k in data},
                "elevation": data.get("elevation"),
                "update_time": data.get("updateTime"),
            }

        # daily (default)
        forecast_data, grid_data = await asyncio.gather(
            _nws.get_forecast(wfo, x, y),
            _nws.get_detailed_forecast(wfo, x, y),
            return_exceptions=True,
        )
        if isinstance(forecast_data, Exception):
            raise forecast_data
        periods = forecast_data.get("periods", [])
        max_periods = days * 2
        periods = periods[:max_periods]

        gd = grid_data if not isinstance(grid_data, Exception) else {}
        if isinstance(grid_data, Exception):
            logger.debug("grid data fetch failed, enriched fields unavailable: %s", grid_data)
        arrays = _extract_grid_arrays(gd, periods)

        result: dict = {
            "location": _location_name(point),
            "periods": [
                _build_forecast_period(p, i, arrays, prefs, include_daily_fields=True)
                for i, p in enumerate(periods)
            ],
        }

        # pressure trend for daily mode
        valid_pressures = [v for v in arrays["pressure"] if v is not None]
        if valid_pressures:
            result["pressure_trend"] = _compute_trend(valid_pressures)

        return result
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        logger.exception("error fetching forecast")
        return {"error": f"failed to fetch forecast: {exc}"}


async def get_alerts(
    latitude: float, longitude: float,
    severity_filter: str | None = None, detail: str = "standard",
    units: str | None = None,
) -> dict:
    """Get active weather alerts."""
    try:
        data = await _nws.get_alerts(latitude, longitude)
        features = data.get("features", [])

        try:
            point = await _nws.get_point(latitude, longitude)
            location = _location_name(point)
        except Exception:
            logger.debug("could not resolve location name", exc_info=True)
            location = f"{latitude}, {longitude}"

        alerts = sorted(
            [f["properties"] for f in features],
            key=lambda a: _SEVERITY_ORDER.get(a.get("severity", "Unknown"), 4),
        )

        if severity_filter:
            alerts = [a for a in alerts if a.get("severity", "").lower() == severity_filter.lower()]

        formatted = []
        for a in alerts:
            entry = {
                "event": a.get("event", "Unknown"),
                "severity": a.get("severity", "Unknown"),
                "headline": a.get("headline", ""),
                "description": a.get("description", ""),
                "instruction": a.get("instruction", ""),
            }
            if detail == "full":
                codes = a.get("geocode", {}).get("UGC", [])
                entry["urgency"] = a.get("urgency", "Unknown")
                entry["certainty"] = a.get("certainty", "Unknown")
                entry["effective"] = a.get("effective", "")
                entry["expires"] = a.get("expires", "")
                entry["sender_name"] = a.get("senderName", "")
                entry["area_desc"] = a.get("areaDesc", "")
                entry["geocode"] = codes
                vtec = a.get("parameters", {}).get("VTEC", [])
                entry["vtec"] = vtec
                geom = None
                for f in features:
                    if f["properties"].get("id") == a.get("id"):
                        geom = f.get("geometry")
                        break
                entry["geometry"] = geom
            formatted.append(entry)

        return {
            "location": location,
            "count": len(formatted),
            "alerts": formatted,
        }
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        logger.exception("error fetching alerts")
        return {"error": f"failed to fetch alerts: {exc}"}


_VALID_OUTLOOK_TYPES = {"categorical", "tornado", "wind", "hail"}


async def get_spc_outlook(
    latitude: float, longitude: float,
    outlook_type: str = "categorical", day: int = 1,
    units: str | None = None,
) -> dict:
    """Get SPC outlook for a point — categorical or probabilistic."""
    if day < 1 or day > 3:
        return {"error": f"invalid day {day}, must be 1-3"}
    if outlook_type not in _VALID_OUTLOOK_TYPES:
        return {"error": f"invalid outlook_type '{outlook_type}', must be one of: categorical, tornado, wind, hail"}
    return await _spc.get_spc_outlook(latitude, longitude, day, outlook_type)


async def get_national_outlook(day: int = 1, units: str | None = None) -> dict:
    """Get CONUS-wide SPC risk areas."""
    if day < 1 or day > 3:
        return {"error": f"invalid day {day}, must be 1-3"}
    return await _spc.get_national_outlook_summary(day)


def _build_radar_summary(obs: dict, hourly_periods: list[dict]) -> str:
    """build a textual summary from observation and hourly forecast."""
    parts = []

    description = obs.get("textDescription", "")
    if description:
        parts.append(description)

    present_weather = obs.get("presentWeather") or []
    phenomena = [
        pw.get("weather", "") for pw in present_weather
        if pw.get("weather")
    ]
    if phenomena:
        parts.append(f"({', '.join(phenomena)})")

    cloud_layers = obs.get("cloudLayers") or []
    for layer in cloud_layers:
        amount = layer.get("amount", "")
        if amount in ("CLR", "SKC"):
            continue
        base = layer.get("base", {})
        base_m = base.get("value") if isinstance(base, dict) else None
        if amount and base_m is not None:
            base_ft = round(base_m * 3.281)
            parts.append(f"{amount} clouds at {base_ft}ft")

    if hourly_periods:
        precip_parts = []
        for p in hourly_periods[:6]:
            prob = p.get("probabilityOfPrecipitation", {})
            val = prob.get("value", 0) or 0
            precip_parts.append((p.get("startTime", ""), val, p.get("shortForecast", "")))

        max_prob = max(v for _, v, _ in precip_parts) if precip_parts else 0
        if max_prob > 0:
            high_periods = [(t, v, f) for t, v, f in precip_parts if v >= max_prob * 0.8]
            if high_periods:
                _, prob, fcst = high_periods[0]
                parts.append(f"Precipitation {prob}% chance in near-term ({fcst})")
        else:
            parts.append("No precipitation expected in the next 6 hours")

    return ". ".join(parts) + "." if parts else "No observation data available."


async def get_radar(latitude: float, longitude: float, units: str | None = None) -> dict:
    """Get NEXRAD radar metadata, textual summary, and clickable links."""
    try:
        point = await _nws.get_point(latitude, longitude)
        radar_station = point.get("radarStation", "")
        if not radar_station:
            return {"error": "no radar station found for this location"}

        wfo, gx, gy = point["gridId"], point["gridX"], point["gridY"]

        radar_task = _iem.get_radar_info(radar_station)

        # fetch observation and hourly forecast for summary
        async def _fetch_obs():
            stations = await _nws.get_stations(point["observationStations"])
            if not stations:
                return {}
            return await _nws.get_latest_observation(stations[0]["stationIdentifier"])

        obs_task = _fetch_obs()
        hourly_task = _nws.get_hourly_forecast(wfo, gx, gy)

        radar_info, obs, hourly = await asyncio.gather(
            radar_task, obs_task, hourly_task, return_exceptions=True,
        )

        if isinstance(radar_info, Exception):
            return {"error": f"failed to fetch radar: {radar_info}"}

        obs = obs if not isinstance(obs, Exception) else {}
        hourly_data = hourly if not isinstance(hourly, Exception) else {}
        hourly_periods = hourly_data.get("periods", []) if isinstance(hourly_data, dict) else []

        summary = _build_radar_summary(obs, hourly_periods)
        current_weather = obs.get("textDescription", "N/A")

        cloud_layers = obs.get("cloudLayers") or []
        if cloud_layers:
            top_layer = cloud_layers[-1].get("amount", "N/A")
        else:
            top_layer = "N/A"

        imagery = radar_info.get("imagery_urls", {})
        links = {}
        if imagery.get("composite_url"):
            links["regional_composite"] = imagery["composite_url"]
        if imagery.get("site_url"):
            links["local_radar"] = imagery["site_url"]

        return {
            "station_id": radar_info.get("station_id", radar_station),
            "latest_scan_time": radar_info.get("latest_scan_time"),
            "available_products": radar_info.get("available_products", []),
            "summary": summary,
            "current_weather": current_weather,
            "cloud_cover": top_layer,
            "links": links,
        }
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        logger.exception("error fetching radar")
        return {"error": f"failed to fetch radar: {exc}"}


async def get_briefing(
    latitude: float, longitude: float, detail: str = "standard",
    units: str | None = None,
) -> dict:
    """Comprehensive weather briefing."""
    tasks = [
        get_conditions(latitude, longitude, detail, units=units),
        get_forecast(latitude, longitude, mode="daily", days=1, units=units),
        get_alerts(latitude, longitude, detail=detail, units=units),
        get_spc_outlook(latitude, longitude, outlook_type="categorical", units=units),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    current = results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])}
    forecast = results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])}
    alerts = results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])}
    severe = results[3] if not isinstance(results[3], Exception) else {"error": str(results[3])}

    summary = {"current_conditions": current, "severe_outlook": severe}

    if "error" not in forecast:
        periods = forecast.get("periods", [])
        summary["location"] = forecast.get("location", "Unknown")
        summary["today"] = periods[0] if len(periods) > 0 else None
        summary["tonight"] = periods[1] if len(periods) > 1 else None
    else:
        summary["location"] = current.get("station_name", "Unknown")
        summary["forecast_error"] = forecast["error"]

    if "error" not in alerts:
        summary["alert_count"] = alerts.get("count", 0)
        summary["alerts"] = alerts.get("alerts", [])
    else:
        summary["alerts_error"] = alerts["error"]

    if detail == "full":
        extra_tasks = []
        risk_level = severe.get("risk_level", "NONE") if isinstance(severe, dict) else "NONE"
        if risk_level not in ("NONE", "TSTM"):
            extra_tasks.append(("probabilistic_tornado", get_spc_outlook(latitude, longitude, "tornado")))
            extra_tasks.append(("probabilistic_wind", get_spc_outlook(latitude, longitude, "wind")))
            extra_tasks.append(("probabilistic_hail", get_spc_outlook(latitude, longitude, "hail")))

        extra_tasks.append(("national_day1", get_national_outlook(1)))
        extra_tasks.append(("radar", get_radar(latitude, longitude)))

        for day in (2, 3):
            extra_tasks.append((f"spc_day{day}", get_spc_outlook(latitude, longitude, "categorical", day)))

        names, coros = zip(*extra_tasks)
        extra_results = await asyncio.gather(*coros, return_exceptions=True)

        for name, res in zip(names, extra_results):
            if isinstance(res, Exception):
                summary[name] = {"error": str(res)}
            else:
                summary[name] = res

    return summary


_ATTRIBUTION = "Weather data by Open-Meteo.com (CC-BY 4.0) — https://open-meteo.com/"


def _fmt_height_dam(gpm: float | None) -> str:
    if gpm is None:
        return "N/A"
    dam = gpm_to_dam(gpm)
    return f"{round(dam)} dam"


def _fmt_upper_wind(speed_ms: float | None, direction: float | None, prefs: UnitPrefs) -> str:
    if speed_ms is None:
        return "N/A"
    if round(speed_ms) == 0:
        return "Calm"
    cardinal = degrees_to_cardinal(direction)
    if prefs.wind == "ms":
        s = round(speed_ms)
        unit = "m/s"
    elif prefs.wind == "kmh":
        s = round(speed_ms * 3.6)
        unit = "km/h"
    elif prefs.wind == "mph":
        s = round(ms_to_mph(speed_ms))
        unit = "mph"
    else:
        s = round(ms_to_kt(speed_ms))
        unit = "kt"
    if cardinal:
        return f"{cardinal} {s} {unit}"
    return f"{s} {unit}"


def _fmt_upper_temp(celsius: float | None, prefs: UnitPrefs) -> str:
    if celsius is None:
        return "N/A"
    if prefs.temperature == "c":
        return f"{round(celsius)}°C"
    f = c_to_f(celsius)
    return f"{round(f)}°F"


def _fmt_vorticity(value: float | None) -> str:
    if value is None:
        return "N/A"
    scaled = value * 1e5
    return f"{scaled:.1f}"


def _compute_trend(values: list[float]) -> str:
    if len(values) < 3:
        return "steady"
    third = len(values) // 3
    first_avg = sum(values[:third]) / third
    last_avg = sum(values[-third:]) / third
    diff = last_avg - first_avg
    data_range = max(values) - min(values) if values else 0
    threshold = abs(first_avg) * 0.02 if first_avg != 0 else data_range * 0.02 or 1e-10
    if diff > threshold:
        return "rising"
    if diff < -threshold:
        return "falling"
    return "steady"


async def get_upper_air(
    latitude: float, longitude: float, units: str | None = None,
) -> dict:
    """get 500mb upper-air analysis with derived vorticity."""
    prefs = parse_units(units, config.units)
    try:
        data = await _openmeteo.get_upper_air(latitude, longitude)
        center = data["center"]
        hourly = center.get("hourly", {})
        times = hourly.get("time", [])
        heights = hourly.get("geopotential_height_500hPa", [])
        temps = hourly.get("temperature_500hPa", [])
        speeds = hourly.get("wind_speed_500hPa", [])
        directions = hourly.get("wind_direction_500hPa", [])

        time_series = []
        height_values = []
        vort_values = []

        def _wind_at(point_key, idx):
            pt = data[point_key].get("hourly", {})
            s = pt.get("wind_speed_500hPa", [])[idx]
            dr = pt.get("wind_direction_500hPa", [])[idx]
            return (s, dr)

        for i in range(len(times)):
            h = heights[i] if i < len(heights) else None
            t = temps[i] if i < len(temps) else None
            spd = speeds[i] if i < len(speeds) else None
            d = directions[i] if i < len(directions) else None

            rel_str = "N/A"
            abs_str = "N/A"
            try:
                center_w = _wind_at("center", i)
                north_w = _wind_at("north", i)
                south_w = _wind_at("south", i)
                east_w = _wind_at("east", i)
                west_w = _wind_at("west", i)

                rel, abso = compute_vorticity(
                    latitude, center_w, north_w, south_w, east_w, west_w,
                )
                if rel is not None:
                    rel_str = _fmt_vorticity(rel)
                    abs_str = _fmt_vorticity(abso)
                    vort_values.append(rel)
            except (IndexError, KeyError, TypeError):
                logger.debug("vorticity computation failed for timestep %d", i, exc_info=True)

            if h is not None:
                height_values.append(h)

            time_series.append({
                "time": times[i],
                "height": _fmt_height_dam(h),
                "temperature": _fmt_upper_temp(t, prefs),
                "wind": _fmt_upper_wind(spd, d, prefs),
                "relative_vorticity": rel_str,
                "absolute_vorticity": abs_str,
            })

        return {
            "latitude": latitude,
            "longitude": longitude,
            "level": "500 hPa",
            "time_series": time_series,
            "height_trend": _compute_trend(height_values),
            "vorticity_trend": _compute_trend(vort_values),
            "attribution": _ATTRIBUTION,
        }
    except Exception as exc:
        logger.exception("error fetching upper-air data")
        return {"error": f"failed to fetch upper-air data: {exc}"}


_EARTH_RADIUS_KM = 6371.0
_KM_PER_MI = 1.609344


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return _EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlon = rlon2 - rlon1
    x = math.sin(dlon) * math.cos(rlat2)
    y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _nearest_point_on_line(lat: float, lon: float, coords: list) -> tuple[float, float, float]:
    """find closest point on a polyline to (lat, lon). returns (nearest_lat, nearest_lon, dist_km)."""
    best_dist = float("inf")
    best_pt = (coords[0][1], coords[0][0])

    for i in range(len(coords) - 1):
        ax, ay = coords[i][0], coords[i][1]
        bx, by = coords[i + 1][0], coords[i + 1][1]
        # project point onto segment in lon/lat space (approximate at
        # high latitudes due to longitude compression, but adequate for
        # CONUS where cos(lat) ~ 0.65-0.91)
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            px, py = ax, ay
        else:
            t = max(0, min(1, ((lon - ax) * dx + (lat - ay) * dy) / (dx * dx + dy * dy)))
            px, py = ax + t * dx, ay + t * dy
        d = _haversine_km(lat, lon, py, px)
        if d < best_dist:
            best_dist = d
            best_pt = (py, px)

    # single-point linestring: loop didn't execute, compute distance to the only point
    if best_dist == float("inf"):
        best_dist = _haversine_km(lat, lon, best_pt[0], best_pt[1])

    return best_pt[0], best_pt[1], best_dist


def _which_side_of_front(lat: float, lon: float, coords: list, front_type: str) -> str | None:
    """determine if point is on warm or cold side of a front.

    uses cross product of front direction with point-to-front vector.
    WPC convention: cold air is to the left of the front direction for cold fronts.
    positive cross product = left side = cold side.

    returns "warm side (ahead of front)" or "cold side (behind front)" for cold fronts,
    or None for non-cold fronts.
    """
    if front_type != "cold":
        return None

    # find the nearest segment
    best_i = 0
    best_dist = float("inf")
    for i in range(len(coords) - 1):
        ax, ay = coords[i][0], coords[i][1]
        bx, by = coords[i + 1][0], coords[i + 1][1]
        mx, my = (ax + bx) / 2, (ay + by) / 2
        d = _haversine_km(lat, lon, my, mx)
        if d < best_dist:
            best_dist = d
            best_i = i

    ax, ay = coords[best_i][0], coords[best_i][1]
    bx, by = coords[best_i + 1][0], coords[best_i + 1][1]
    # front direction vector
    fdx, fdy = bx - ax, by - ay
    # vector from segment start to point
    pdx, pdy = lon - ax, lat - ay
    cross = fdx * pdy - fdy * pdx

    if cross > 0:
        return "cold side (behind front)"
    return "warm side (ahead of front)"


def _fmt_distance(km: float, prefs: UnitPrefs) -> str:
    if prefs.distance == "km":
        return f"{round(km)} km"
    mi = km / _KM_PER_MI
    return f"{round(mi)} mi"


async def get_surface_analysis(
    latitude: float, longitude: float, day: int = 1, detail: str = "standard",
    units: str | None = None,
) -> dict:
    """get WPC surface analysis with fronts and pressure centers."""
    if day < 1 or day > 3:
        return {"error": f"invalid day {day}, must be 1-3"}
    prefs = parse_units(units, config.units)
    try:
        fronts_data, centers_data = await _wpc.get_surface_analysis(day)

        parsed_fronts = []
        for feat in fronts_data.get("features", []):
            props = feat.get("properties", {})
            feat_type = FRONT_TYPES.get(props.get("feat", ""))
            if feat_type is None:
                continue
            geom = feat.get("geometry", {})
            geom_type = geom.get("type", "")
            raw_coords = geom.get("coordinates", [])
            if not raw_coords:
                continue
            # flatten MultiLineString into a single coordinate list
            if geom_type == "MultiLineString":
                coords = [pt for segment in raw_coords for pt in segment]
            else:
                coords = raw_coords
            if not coords:
                continue
            nlat, nlon, dist = _nearest_point_on_line(latitude, longitude, coords)
            bearing = _bearing_deg(latitude, longitude, nlat, nlon)
            cardinal = degrees_to_cardinal(bearing)
            entry = {
                "type": feat_type,
                "distance": _fmt_distance(dist, prefs),
                "distance_km": round(dist, 1),
                "bearing": cardinal,
            }
            side = _which_side_of_front(latitude, longitude, coords, feat_type)
            if side:
                entry["position"] = side
            if detail == "full":
                entry["nearest_point"] = {"latitude": round(nlat, 4), "longitude": round(nlon, 4)}
                entry["geometry_type"] = geom_type
            parsed_fronts.append(entry)

        parsed_centers = []
        for feat in centers_data.get("features", []):
            props = feat.get("properties", {})
            center_type = CENTER_TYPES.get(props.get("feat", ""))
            if center_type is None:
                continue
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [])
            if not coords or len(coords) < 2:
                continue
            clat, clon = coords[1], coords[0]
            dist = _haversine_km(latitude, longitude, clat, clon)
            bearing = _bearing_deg(latitude, longitude, clat, clon)
            cardinal = degrees_to_cardinal(bearing)
            entry = {
                "type": center_type,
                "distance": _fmt_distance(dist, prefs),
                "distance_km": round(dist, 1),
                "bearing": cardinal,
            }
            if detail == "full":
                entry["coordinates"] = {"latitude": round(clat, 4), "longitude": round(clon, 4)}
            parsed_centers.append(entry)

        parsed_fronts.sort(key=lambda f: f["distance_km"])
        parsed_centers.sort(key=lambda c: c["distance_km"])

        # build location summary from nearest cold front
        location_summary = None
        for fr in parsed_fronts:
            if fr["type"] == "cold" and fr.get("position"):
                location_summary = f"{fr['position']} — cold front {fr['distance']} to the {fr['bearing']}"
                break

        result: dict = {
            "day": day,
        }
        if location_summary:
            result["location_summary"] = location_summary
        if detail == "standard":
            result["nearest_fronts"] = parsed_fronts[:5]
            result["nearest_pressure_centers"] = parsed_centers[:4]
        else:
            result["nearest_fronts"] = parsed_fronts
            result["nearest_pressure_centers"] = parsed_centers

        return result
    except Exception as exc:
        logger.exception("error fetching surface analysis")
        return {"error": f"failed to fetch surface analysis: {exc}"}

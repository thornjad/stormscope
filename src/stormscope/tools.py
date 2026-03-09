"""Weather tool functions for the MCP server."""

import asyncio
import logging

from stormscope.config import config
from stormscope.iem import IEMClient
from stormscope.nws import NWSClient
from stormscope.openmeteo import OpenMeteoClient
from stormscope.spc import SPCClient
from stormscope.units import c_to_f, degrees_to_cardinal, gpm_to_dam, kmh_to_mph, m_to_miles, ms_to_kt, pa_to_inhg
from stormscope.vorticity import compute_vorticity

logger = logging.getLogger(__name__)

_nws = NWSClient()
_spc = SPCClient()
_iem = IEMClient()
_openmeteo = OpenMeteoClient()


async def shutdown():
    """close all HTTP clients."""
    await _nws.close()
    await _spc.close()
    await _iem.close()
    await _openmeteo.close()


def _is_si() -> bool:
    return config.units == "si"


def _obs_value(obs: dict, field: str) -> float | None:
    entry = obs.get(field)
    if entry is None:
        return None
    return entry.get("value")


def _fmt_temp(fahrenheit: float | None, celsius: float | None = None) -> str:
    if _is_si():
        if celsius is None:
            return "N/A"
        return f"{round(celsius)}°C"
    if fahrenheit is None:
        return "N/A"
    return f"{round(fahrenheit)}°F"


def _fmt_wind(speed: float | None, direction: str | None) -> str:
    if speed is None:
        return "Calm"
    s = round(speed)
    if s == 0:
        return "Calm"
    unit = "km/h" if _is_si() else "mph"
    if direction:
        return f"{direction} {s} {unit}"
    return f"{s} {unit}"


def _fmt_humidity(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{round(value)}%"


def _fmt_visibility(miles: float | None, meters: float | None = None) -> str:
    if _is_si():
        if meters is None:
            return "N/A"
        km = meters / 1000
        return f"{km:.1f} km"
    if miles is None:
        return "N/A"
    return f"{miles:.1f} mi"


def _fmt_pressure(inhg: float | None, pascals: float | None = None) -> str:
    if _is_si():
        if pascals is None:
            return "N/A"
        hpa = pascals / 100
        return f"{hpa:.1f} hPa"
    if inhg is None:
        return "N/A"
    return f"{inhg:.2f} inHg"


def _fmt_gust(speed: float | None) -> str:
    if speed is None:
        return "calm"
    unit = "km/h" if _is_si() else "mph"
    return f"{round(speed)} {unit}"


def _location_name(point: dict) -> str:
    rel = point.get("relativeLocation", {}).get("properties", {})
    city = rel.get("city", "Unknown")
    state = rel.get("state", "")
    if state:
        return f"{city}, {state}"
    return city


_SEVERITY_ORDER = {
    "Extreme": 0,
    "Severe": 1,
    "Moderate": 2,
    "Minor": 3,
    "Unknown": 4,
}


async def get_conditions(
    latitude: float, longitude: float, detail: str = "standard",
) -> dict:
    """Get current weather conditions."""
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

        wind_speed = wind_kmh if _is_si() else kmh_to_mph(wind_kmh)
        gust_speed = gust_kmh if _is_si() else kmh_to_mph(gust_kmh)
        cardinal = degrees_to_cardinal(wind_deg)

        result = {
            "temperature": _fmt_temp(temp_f, temp_c),
            "feels_like": _fmt_temp(feels_like_f, feels_like_c if feels_like_c is not None else temp_c),
            "humidity": _fmt_humidity(humidity),
            "wind": _fmt_wind(wind_speed, cardinal),
            "wind_gust": _fmt_gust(gust_speed),
            "sky_condition": obs.get("textDescription", "N/A"),
            "visibility": _fmt_visibility(m_to_miles(vis_m), vis_m),
            "pressure": _fmt_pressure(pa_to_inhg(pressure_pa), pressure_pa),
            "station_name": station.get("name", "Unknown"),
            "observation_time": obs.get("timestamp", "N/A"),
        }

        if detail == "full":
            dewpoint_c = _obs_value(obs, "dewpoint")
            dewpoint_f = c_to_f(dewpoint_c)
            result["dewpoint"] = _fmt_temp(dewpoint_f, dewpoint_c)
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


async def get_forecast(
    latitude: float, longitude: float,
    mode: str = "daily", days: int = 7, hours: int = 24,
) -> dict:
    """Get forecast: daily (12h periods), hourly, or raw gridpoint data."""
    if mode not in _VALID_MODES:
        return {"error": f"invalid mode '{mode}', must be one of: daily, hourly, raw"}
    try:
        point = await _nws.get_point(latitude, longitude)
        wfo, x, y = point["gridId"], point["gridX"], point["gridY"]

        if mode == "hourly":
            data = await _nws.get_hourly_forecast(wfo, x, y)
            periods = data.get("periods", [])[:hours]
            return {
                "location": _location_name(point),
                "periods": [
                    {
                        "start_time": p["startTime"],
                        "temperature": f"{p['temperature']}°{p['temperatureUnit']}",
                        "wind": f"{p['windDirection']} {p['windSpeed']}",
                        "forecast": p["shortForecast"],
                        "precipitation_chance": f"{p.get('probabilityOfPrecipitation', {}).get('value', 0) or 0}%",
                    }
                    for p in periods
                ],
            }

        if mode == "raw":
            data = await _nws.get_detailed_forecast(wfo, x, y)
            params = [
                "temperature", "dewpoint", "windSpeed", "windDirection",
                "probabilityOfPrecipitation", "skyCover", "weather",
            ]
            return {
                "location": _location_name(point),
                "grid": {k: data.get(k) for k in params if k in data},
                "elevation": data.get("elevation"),
                "update_time": data.get("updateTime"),
            }

        # daily (default)
        data = await _nws.get_forecast(wfo, x, y)
        periods = data.get("periods", [])
        max_periods = days * 2
        periods = periods[:max_periods]

        return {
            "location": _location_name(point),
            "periods": [
                {
                    "name": p["name"],
                    "temperature": f"{p['temperature']}°{p['temperatureUnit']}",
                    "wind": f"{p['windDirection']} {p['windSpeed']}",
                    "forecast": p["shortForecast"],
                    "detailed": p["detailedForecast"],
                    "is_daytime": p["isDaytime"],
                }
                for p in periods
            ],
        }
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        logger.exception("error fetching forecast")
        return {"error": f"failed to fetch forecast: {exc}"}


async def get_alerts(
    latitude: float, longitude: float,
    severity_filter: str | None = None, detail: str = "standard",
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
) -> dict:
    """Get SPC outlook for a point — categorical or probabilistic."""
    if day < 1 or day > 3:
        return {"error": f"invalid day {day}, must be 1-3"}
    if outlook_type not in _VALID_OUTLOOK_TYPES:
        return {"error": f"invalid outlook_type '{outlook_type}', must be one of: categorical, tornado, wind, hail"}
    return await _spc.get_spc_outlook(latitude, longitude, day, outlook_type)


async def get_national_outlook(day: int = 1) -> dict:
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


async def get_radar(latitude: float, longitude: float) -> dict:
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
) -> dict:
    """Comprehensive weather briefing."""
    tasks = [
        get_conditions(latitude, longitude, detail),
        get_forecast(latitude, longitude, mode="daily", days=1),
        get_alerts(latitude, longitude, detail=detail),
        get_spc_outlook(latitude, longitude, outlook_type="categorical"),
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


def _fmt_upper_wind(speed_ms: float | None, direction: float | None) -> str:
    if speed_ms is None:
        return "N/A"
    if round(speed_ms) == 0:
        return "Calm"
    cardinal = degrees_to_cardinal(direction)
    if _is_si():
        s = round(speed_ms)
        unit = "m/s"
    else:
        s = round(ms_to_kt(speed_ms))
        unit = "kt"
    if cardinal:
        return f"{cardinal} {s} {unit}"
    return f"{s} {unit}"


def _fmt_upper_temp(celsius: float | None) -> str:
    if celsius is None:
        return "N/A"
    if _is_si():
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
    threshold = abs(first_avg) * 0.02 if first_avg != 0 else 0.01
    if diff > threshold:
        return "rising"
    if diff < -threshold:
        return "falling"
    return "steady"


async def get_upper_air(latitude: float, longitude: float) -> dict:
    """get 500mb upper-air analysis with derived vorticity."""
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

        for i in range(len(times)):
            h = heights[i] if i < len(heights) else None
            t = temps[i] if i < len(temps) else None
            spd = speeds[i] if i < len(speeds) else None
            d = directions[i] if i < len(directions) else None

            # extract winds from all 5 points for vorticity
            rel_str = "N/A"
            abs_str = "N/A"
            try:
                def _wind_at(point_key, idx):
                    pt = data[point_key].get("hourly", {})
                    s = pt.get("wind_speed_500hPa", [])[idx]
                    dr = pt.get("wind_direction_500hPa", [])[idx]
                    return (s, dr)

                center_w = _wind_at("center", i)
                north_w = _wind_at("north", i)
                south_w = _wind_at("south", i)
                east_w = _wind_at("east", i)
                west_w = _wind_at("west", i)

                rel, abso = compute_vorticity(
                    latitude, center_w, north_w, south_w, east_w, west_w,
                )
                rel_str = _fmt_vorticity(rel)
                abs_str = _fmt_vorticity(abso)
                vort_values.append(rel)
            except (IndexError, KeyError, TypeError):
                pass

            if h is not None:
                height_values.append(h)

            time_series.append({
                "time": times[i],
                "height": _fmt_height_dam(h),
                "temperature": _fmt_upper_temp(t),
                "wind": _fmt_upper_wind(spd, d),
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

# Changelog

## 1.1.0

- add `get_upper_air` tool for 500mb analysis (heights, temperature, wind, vorticity) via Open-Meteo
- add `OpenMeteoClient` for pressure-level model data with TTL caching and stale fallback
- add vorticity module with 5-point finite-difference computation

## 1.0.0

- remove hostname from user-agent string for privacy
- add debug logging to silent except blocks in SPC and tools modules
- wrap blocking subprocess call in `asyncio.to_thread`
- add max size eviction to TTL cache (default 256 entries)
- add input validation for lat/lon bounds, detail level, forecast days/hours
- add NWS URL host allowlist to prevent SSRF
- add `get_or_fetch` helper to TTL cache to reduce duplication
- extract `BaseAPIClient` shared by NWS, SPC, and IEM clients
- add `__main__.py` for `python -m stormscope` support
- migrate IEM tests from `patch.object` to `respx`
- bump development status to Production/Stable

## 0.10.0

- add `get_radar` tool with textual weather summary and clickable imagery links
- add `get_briefing` comprehensive weather briefing tool
- add `get_national_outlook` for CONUS-wide SPC risk areas
- add probabilistic SPC outlook support (tornado/wind/hail)
- add SI unit support via `UNITS=si` environment variable
- add CoreLocation geolocation for macOS (opt-in)
- add IP-based geolocation fallback
- add full detail mode for conditions, alerts, and briefings

## 0.9.0

- initial release with `get_conditions`, `get_forecast`, `get_alerts`, `get_spc_outlook`
- NWS API client with TTL caching and retry logic
- SPC categorical outlook with point-in-polygon checking
- async architecture with httpx

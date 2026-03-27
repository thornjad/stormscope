# Changelog

## 1.4.2

- fix surface analysis using forecast bulletin instead of current conditions; parse CODSUS coded bulletin for actual current analysis
- fix single-coord front IndexError in surface analysis
- fix IEM mislabeling and continuation line parsing
- preserve forecast analysis as separate `scope` parameter

## 1.4.1

- handle SPC 404 as missing outlook instead of error

## 1.4.0

- enrich hourly forecasts with Tempest hourly sensor data when station is in range
- suppress `none` precip_type from hourly enrichment output

## 1.3.0

- add WeatherFlow Tempest personal weather station integration with hyper-local sensor enrichment
- add `sensor_divergence` warning when Tempest and NWS temperatures differ significantly
- add out-of-range warning when configured Tempest station exceeds 5-mile proximity threshold
- always prefer Tempest values when station is within range
- add `USE_TEMPEST_STATION_GEOLOCATION` option to use Tempest station location as primary
- improve caching behavior for non-Tempest locations
- fix null GeoJSON geometry crash in `get_surface_analysis`
- fix `normalize_obs` to always read observation data as SI before converting
- add coverage reporting via GitHub Actions
- raise test coverage threshold to 85%

## 1.2.0

- add `get_surface_analysis` tool for WPC frontal analysis, surface lows/highs, and warm/cold sector detection
- add units parameter to all MCP tool registrations
- add `UnitPrefs` dataclass and `parse_units` helper
- enrich forecasts with unit-aware fields
- handle MultiLineString geometry from WPC MapServer

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

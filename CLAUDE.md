# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

stormscope is a real-time US weather data MCP server. It aggregates data from NWS (National Weather Service), NOAA SPC (Storm Prediction Center), and Iowa Environmental Mesonet (NEXRAD radar) into 7 tools consumed by AI assistants via the FastMCP framework.

## Commands

```bash
uv sync --group dev              # install all dependencies including dev
uv run python -m pytest          # run all tests
uv run python -m pytest tests/test_nws.py           # run a single test file
uv run python -m pytest tests/test_nws.py -k "test_name"  # run a single test
```

There is no separate build or lint step. The project uses `hatchling` as build backend but day-to-day development is just edit-and-test. Requires Python >=3.11.

## Architecture

All code lives in `src/stormscope/`. The server exposes 7 async MCP tools defined in `server.py`, with implementations in `tools.py` that aggregate results from three data-source clients:

- **`nws.py`** — NWS API client (conditions, forecasts, alerts, gridpoint data). Has per-endpoint TTL caching and retry logic.
- **`spc.py`** — SPC outlook client. Parses GeoJSON for categorical and probabilistic severe weather risk (tornado/wind/hail), days 1-3.
- **`iem.py`** — Iowa Mesonet client for NEXRAD radar station metadata and imagery URLs.

Supporting modules:
- **`geo.py`** — Location resolution with a fallback chain: explicit params → env vars → macOS CoreLocation (opt-in Swift helper) → IP geolocation. Also converts SPC risk polygons to human-readable region descriptions using Shapely.
- **`cache.py`** — In-memory async TTL cache that returns stale data on fetch failure for API resilience.
- **`config.py`** — Environment variable configuration (`PRIMARY_LATITUDE`, `PRIMARY_LONGITUDE`, `UNITS`, `ENABLE_CORELOCATION`, `DISABLE_AUTO_GEOLOCATION`).
- **`units.py`** — Unit conversion helpers (temperature, wind, distance, pressure, cardinal directions).

## Testing

Tests are in `tests/` with async fixtures in `conftest.py`. HTTP calls are mocked with `respx`. pytest runs in `asyncio_mode = "auto"` so all async tests run without manual decoration.

## Key Patterns

- Fully async — all I/O uses httpx, subprocess, and async filesystem access.
- TTL caching with stale-data fallback — expired cache entries are retained and served when upstream APIs fail.
- Every tool accepts optional `latitude`/`longitude` overrides; otherwise the configured primary location is used.
- US-only — designed for 50 states, DC, and territories. State boundary data lives in `src/stormscope/data/us_states.json`.

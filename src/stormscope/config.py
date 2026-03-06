"""Environment-based configuration."""

import logging
import os
import platform
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_VALID_UNITS = {"us", "si"}


def _build_user_agent() -> str:
    host = platform.node() or "unknown"
    return f"(stormscope/{host}, https://github.com/thornjad/stormscope)"


def _parse_coord(name: str) -> float | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        logger.warning("invalid %s value %r, ignoring", name, raw)
        return None


@dataclass(frozen=True)
class Config:
    primary_latitude: float | None
    primary_longitude: float | None
    units: str
    user_agent: str
    disable_auto_geolocation: bool
    enable_corelocation: bool

    @classmethod
    def from_env(cls) -> "Config":
        units = os.environ.get("UNITS", "us").lower()
        if units not in _VALID_UNITS:
            logger.warning("unrecognized UNITS value %r, defaulting to 'us'", units)
            units = "us"

        disable_geo = os.environ.get(
            "DISABLE_AUTO_GEOLOCATION", ""
        ).lower() in ("true", "1", "yes")

        enable_cl = os.environ.get(
            "ENABLE_CORELOCATION", ""
        ).lower() in ("true", "1", "yes")

        return cls(
            primary_latitude=_parse_coord("PRIMARY_LATITUDE"),
            primary_longitude=_parse_coord("PRIMARY_LONGITUDE"),
            units=units,
            user_agent=_build_user_agent(),
            disable_auto_geolocation=disable_geo,
            enable_corelocation=enable_cl,
        )


config = Config.from_env()

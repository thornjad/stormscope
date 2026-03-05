"""Environment-based configuration."""

import os
import platform
from dataclasses import dataclass


def _build_user_agent() -> str:
    host = platform.node() or "unknown"
    return f"(stormscope/{host}, https://github.com/thornjad/stormscope)"


@dataclass(frozen=True)
class Config:
    primary_latitude: float | None
    primary_longitude: float | None
    units: str
    user_agent: str

    @classmethod
    def from_env(cls) -> "Config":
        lat = os.environ.get("PRIMARY_LATITUDE")
        lon = os.environ.get("PRIMARY_LONGITUDE")
        units = os.environ.get("UNITS", "us").lower()

        return cls(
            primary_latitude=float(lat) if lat else None,
            primary_longitude=float(lon) if lon else None,
            units=units,
            user_agent=_build_user_agent(),
        )


config = Config.from_env()

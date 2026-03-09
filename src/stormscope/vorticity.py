"""vorticity computation from 5-point finite-difference wind fields."""

import math

_OMEGA = 7.2921e-5  # Earth's angular velocity (rad/s)
_R_EARTH = 6.371e6  # mean Earth radius (m)


def wind_components(speed_ms: float, direction_deg: float) -> tuple[float, float]:
    """decompose meteorological wind to (u, v) in m/s.

    Meteorological convention: direction is where wind comes FROM,
    measured clockwise from north.
    u = eastward component, v = northward component.
    """
    rad = math.radians(direction_deg)
    u = -speed_ms * math.sin(rad)
    v = -speed_ms * math.cos(rad)
    return u, v


def grid_spacing(lat_deg: float) -> tuple[float, float]:
    """meters per degree at given latitude for 1-degree spacing.

    Returns (dx, dy) where dx shrinks with cos(lat).
    """
    lat_rad = math.radians(lat_deg)
    dy = math.radians(1.0) * _R_EARTH
    dx = dy * math.cos(lat_rad)
    return dx, dy


def coriolis_parameter(lat_deg: float) -> float:
    """Coriolis parameter f = 2 * omega * sin(lat)."""
    return 2.0 * _OMEGA * math.sin(math.radians(lat_deg))


def compute_vorticity(
    lat: float,
    center_wind: tuple[float, float],
    north_wind: tuple[float, float],
    south_wind: tuple[float, float],
    east_wind: tuple[float, float],
    west_wind: tuple[float, float],
) -> tuple[float, float]:
    """compute relative and absolute vorticity from a 5-point cross pattern.

    Each wind arg is (speed_ms, direction_deg). Center wind is accepted for
    API clarity but only cardinal points are used in finite differences.

    Returns (relative_vorticity, absolute_vorticity) in s^-1.
    Returns (None, None) for latitudes beyond 85 degrees where the
    finite-difference grid spacing becomes degenerate.
    """
    if abs(lat) > 85:
        return None, None

    dx, dy = grid_spacing(lat)

    u_n, v_n = wind_components(*north_wind)
    u_s, v_s = wind_components(*south_wind)
    u_e, v_e = wind_components(*east_wind)
    u_w, v_w = wind_components(*west_wind)

    # centered finite differences: dv/dx - du/dy
    dvdx = (v_e - v_w) / (2.0 * dx)
    dudy = (u_n - u_s) / (2.0 * dy)

    relative = dvdx - dudy
    absolute = relative + coriolis_parameter(lat)
    return relative, absolute

"""Thermodynamic and kinematic indices from a sounding profile, via MetPy.

Levels are dicts ordered surface-first with keys: pressure (mb), height (m MSL),
temp (C), dewpoint (C), wind_dir (deg), wind_speed (kt). Any value except
pressure and height may be None.
"""

import logging
import warnings

import numpy as np
from metpy import calc
from metpy.units import units

logger = logging.getLogger(__name__)


def clean_profile(levels: list[dict]) -> list[dict]:
    """keep levels with usable thermo data, strictly decreasing in pressure."""
    out: list[dict] = []
    for lv in levels:
        if lv.get("temp") is None or lv.get("dewpoint") is None:
            continue
        if lv.get("pressure") is None or lv.get("height") is None:
            continue
        if out and lv["pressure"] >= out[-1]["pressure"]:
            continue
        out.append(lv)
    return out


def _interp_log_p(p_target: float, pressures: np.ndarray, values: np.ndarray) -> float | None:
    """interpolate values at a pressure, linear in ln(p). None if out of range."""
    if p_target > pressures[0] or p_target < pressures[-1]:
        return None
    # np.interp needs increasing x, and ln(p) decreases with height
    return float(np.interp(-np.log(p_target), -np.log(pressures), values))


def _agl_at_pressure(p, pressures: np.ndarray, agl: np.ndarray) -> float | None:
    if p is None:
        return None
    return _interp_log_p(float(p.to("hPa").magnitude), pressures, agl)


def _lapse_rate(p_low: float, p_high: float, pressures, temps, agl) -> float | None:
    t_low = _interp_log_p(p_low, pressures, temps)
    t_high = _interp_log_p(p_high, pressures, temps)
    z_low = _interp_log_p(p_low, pressures, agl)
    z_high = _interp_log_p(p_high, pressures, agl)
    if None in (t_low, t_high, z_low, z_high) or z_high <= z_low:
        return None
    return (t_low - t_high) / ((z_high - z_low) / 1000.0)


def _freezing_level_agl(temps: np.ndarray, agl: np.ndarray) -> float | None:
    """lowest height where the profile crosses 0C going up, in m AGL."""
    for i in range(len(temps) - 1):
        t0, t1 = temps[i], temps[i + 1]
        if t0 > 0 >= t1:
            frac = t0 / (t0 - t1)
            return float(agl[i] + frac * (agl[i + 1] - agl[i]))
    if temps[0] <= 0:
        return 0.0
    return None


def _safe(fn):
    """run a metpy calc, returning None on any failure (sparse or odd profiles)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return fn()
    except Exception:
        logger.debug("sounding index calculation failed", exc_info=True)
        return None


def _round(value, digits: int = 1) -> float | None:
    if value is None:
        return None
    value = float(value)
    return None if np.isnan(value) else round(value, digits)


def compute_indices(levels: list[dict]) -> dict:
    """compute stability, moisture, and shear indices for a surface-based parcel.

    every index is independent and reports None when it can't be computed, so a
    sparse profile still yields whatever is available.
    """
    prof = clean_profile(levels)
    empty = {
        "cape_jkg": None, "cin_jkg": None, "lcl_agl_m": None, "lfc_agl_m": None,
        "el_agl_m": None, "freezing_level_agl_m": None,
        "lapse_rate_700_500_c_km": None, "lapse_rate_850_500_c_km": None,
        "pwat_mm": None, "shear_0_1km_kt": None, "shear_0_6km_kt": None,
        "srh_0_1km": None, "srh_0_3km": None,
    }
    if len(prof) < 3:
        return empty

    pres = np.array([lv["pressure"] for lv in prof])
    temp = np.array([lv["temp"] for lv in prof])
    dwpt = np.array([lv["dewpoint"] for lv in prof])
    agl = np.array([lv["height"] for lv in prof]) - prof[0]["height"]

    p_u = pres * units.hPa
    t_u = temp * units.degC
    td_u = dwpt * units.degC

    result = dict(empty)

    cape_cin = _safe(lambda: calc.surface_based_cape_cin(p_u, t_u, td_u))
    if cape_cin is not None:
        result["cape_jkg"] = _round(cape_cin[0].to("J/kg").magnitude, 0)
        result["cin_jkg"] = _round(cape_cin[1].to("J/kg").magnitude, 0)

    lcl = _safe(lambda: calc.lcl(p_u[0], t_u[0], td_u[0]))
    if lcl is not None:
        result["lcl_agl_m"] = _round(_agl_at_pressure(lcl[0], pres, agl), 0)

    lfc = _safe(lambda: calc.lfc(p_u, t_u, td_u))
    if lfc is not None:
        result["lfc_agl_m"] = _round(_agl_at_pressure(lfc[0], pres, agl), 0)

    el = _safe(lambda: calc.el(p_u, t_u, td_u))
    if el is not None:
        result["el_agl_m"] = _round(_agl_at_pressure(el[0], pres, agl), 0)

    # a parcel with no buoyancy has no meaningful LFC/EL, only numerical noise
    if result["cape_jkg"] is not None and result["cape_jkg"] < 1:
        result["lfc_agl_m"] = None
        result["el_agl_m"] = None

    result["freezing_level_agl_m"] = _round(_freezing_level_agl(temp, agl), 0)
    result["lapse_rate_700_500_c_km"] = _round(_lapse_rate(700, 500, pres, temp, agl))
    result["lapse_rate_850_500_c_km"] = _round(_lapse_rate(850, 500, pres, temp, agl))

    pwat = _safe(lambda: calc.precipitable_water(p_u, td_u))
    if pwat is not None:
        result["pwat_mm"] = _round(pwat.to("mm").magnitude)

    result.update(_wind_indices(prof))
    return result


def find_inversions(
    levels: list[dict], max_base_agl_m: float = 5000.0, min_delta_c: float = 0.5,
) -> list[dict]:
    """temperature inversions (warming with height) with a base below max_base_agl_m.

    a layer starts where temperature first rises and continues through any
    isothermal levels, so a stack of tiny warming steps reads as one inversion.
    layers warming less than min_delta_c are dropped as sounding noise.
    """
    prof = clean_profile(levels)
    if len(prof) < 2:
        return []
    sfc_height = prof[0]["height"]
    out: list[dict] = []
    i = 0
    while i < len(prof) - 1:
        if prof[i + 1]["temp"] <= prof[i]["temp"]:
            i += 1
            continue
        start, end = i, i + 1
        while end < len(prof) - 1 and prof[end + 1]["temp"] >= prof[end]["temp"]:
            end += 1
        # drop trailing isothermal levels so the top is where warming actually stops
        while end > start + 1 and prof[end]["temp"] <= prof[end - 1]["temp"]:
            end -= 1
        base, top = prof[start], prof[end]
        delta = top["temp"] - base["temp"]
        if delta >= min_delta_c and base["height"] - sfc_height < max_base_agl_m:
            out.append({
                "surface_based": start == 0,
                "base_agl_m": round(base["height"] - sfc_height),
                "top_agl_m": round(top["height"] - sfc_height),
                "base_pressure_mb": base["pressure"],
                "top_pressure_mb": top["pressure"],
                "delta_c": round(delta, 1),
            })
        i = end
    return out


def _wind_indices(prof: list[dict]) -> dict:
    out = {"shear_0_1km_kt": None, "shear_0_6km_kt": None, "srh_0_1km": None, "srh_0_3km": None}
    windy = [
        lv for lv in prof
        if lv.get("wind_dir") is not None and lv.get("wind_speed") is not None
    ]
    if len(windy) < 3:
        return out

    sfc_height = prof[0]["height"]
    pres = np.array([lv["pressure"] for lv in windy]) * units.hPa
    agl = (np.array([lv["height"] for lv in windy]) - sfc_height) * units.m
    speed = np.array([lv["wind_speed"] for lv in windy]) * units.knot
    direction = np.array([lv["wind_dir"] for lv in windy]) * units.degree
    u, v = calc.wind_components(speed, direction)

    for key, top in (("shear_0_1km_kt", 1000.0), ("shear_0_6km_kt", 6000.0)):
        if agl[-1].magnitude < top:
            continue
        shear = _safe(lambda: calc.bulk_shear(pres, u, v, height=agl, depth=top * units.m))
        if shear is not None:
            su, sv = shear
            out[key] = _round(np.hypot(su.to("knot").magnitude, sv.to("knot").magnitude))

    storm = _safe(lambda: calc.bunkers_storm_motion(pres, u, v, agl))
    if storm is not None:
        right_mover = storm[0]
        for key, top in (("srh_0_1km", 1000.0), ("srh_0_3km", 3000.0)):
            if agl[-1].magnitude < top:
                continue
            srh = _safe(lambda: calc.storm_relative_helicity(
                agl, u, v, depth=top * units.m,
                storm_u=right_mover[0], storm_v=right_mover[1],
            ))
            if srh is not None:
                out[key] = _round(srh[2].to("m^2/s^2").magnitude, 0)
    return out

"""Geohash in pure Python.

Why: "places near me" becomes a prefix range query on an indexed text column
instead of scanning every place. Precision 7 is about 153 m x 153 m; we search
the 9 precision-6 cells around a point, then check real distance.
"""
import math

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def encode(lat: float, lng: float, precision: int = 7) -> str:
    lat_rng, lng_rng = [-90.0, 90.0], [-180.0, 180.0]
    out, bits, bit_count, even = [], 0, 0, True
    while len(out) < precision:
        rng, val = (lng_rng, lng) if even else (lat_rng, lat)
        mid = (rng[0] + rng[1]) / 2
        if val >= mid:
            bits = (bits << 1) | 1
            rng[0] = mid
        else:
            bits <<= 1
            rng[1] = mid
        even = not even
        bit_count += 1
        if bit_count == 5:
            out.append(_BASE32[bits])
            bits, bit_count = 0, 0
    return "".join(out)


def cell_size_deg(precision: int) -> tuple[float, float]:
    """(lat_degrees, lng_degrees) covered by one cell at this precision."""
    total_bits = precision * 5
    lng_bits = math.ceil(total_bits / 2)
    lat_bits = total_bits // 2
    return 180.0 / (2 ** lat_bits), 360.0 / (2 ** lng_bits)


def neighbour_prefixes(lat: float, lng: float, precision: int = 6) -> set[str]:
    """The cell containing the point plus its 8 neighbours."""
    dlat, dlng = cell_size_deg(precision)
    cells = set()
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            la = max(-89.999999, min(89.999999, lat + i * dlat))
            ln = ((lng + j * dlng + 180.0) % 360.0) - 180.0
            cells.add(encode(la, ln, precision))
    return cells


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

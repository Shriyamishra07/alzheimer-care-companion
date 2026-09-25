"""Place index: group memories saved within ~150 m into one Place.

On save: look only at places in the 9 neighbouring geohash cells (an indexed
prefix query), pick the nearest within the radius, or create a new Place.
"""
from datetime import datetime

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import settings
from ..domain import geohash as gh
from ..models import Place

_geo_cache: dict[str, str | None] = {}


def reverse_geocode(lat: float, lng: float) -> str | None:
    """Friendly name from OpenStreetMap Nominatim (free, no key). Cached per ~150 m cell."""
    if settings.GEOCODER != "nominatim":
        return None
    key = gh.encode(lat, lng, 7)
    if key in _geo_cache:
        return _geo_cache[key]
    name = None
    try:
        r = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "jsonv2", "lat": lat, "lon": lng, "zoom": 18, "addressdetails": 1},
            headers={"User-Agent": "AlzheimerCareCompanion/0.6 (BE project, Terna Engineering College)"},
            timeout=4.0,
        )
        if r.status_code == 200:
            data = r.json()
            addr = data.get("address", {})
            first = data.get("name") or next(
                (addr[k] for k in ("amenity", "leisure", "tourism", "shop", "building", "road") if addr.get(k)), None)
            area = next((addr[k] for k in ("suburb", "neighbourhood", "city_district", "city", "town") if addr.get(k)), None)
            if first and area and area not in first:
                name = f"{first}, {area}"
            else:
                name = first or area
    except Exception:
        name = None
    _geo_cache[key] = name
    return name


def places_near(db: Session, user_id: int, lat: float, lng: float, radius_m: float) -> list[tuple[Place, float]]:
    prefixes = gh.neighbour_prefixes(lat, lng, 6)
    rows = (
        db.query(Place)
        .filter(Place.user_id == user_id, or_(*[Place.geohash.startswith(p) for p in prefixes]))
        .all()
    )
    found = [(p, gh.haversine_m(lat, lng, p.lat, p.lng)) for p in rows]
    return sorted([f for f in found if f[1] <= radius_m], key=lambda f: f[1])


def assign_place(db: Session, user_id: int, lat: float, lng: float, when: datetime | None = None) -> Place:
    when = when or datetime.utcnow()
    near = places_near(db, user_id, lat, lng, settings.PLACE_RADIUS_M)
    if near:
        place = near[0][0]
        n = place.record_count or 0
        # Move the centre slightly toward the new point (running mean), keep geohash in sync.
        place.lat = (place.lat * n + lat) / (n + 1)
        place.lng = (place.lng * n + lng) / (n + 1)
        place.geohash = gh.encode(place.lat, place.lng, 7)
        place.record_count = n + 1
        place.last_visit_at = max(place.last_visit_at or when, when)
        return place
    count = db.query(Place).filter(Place.user_id == user_id).count()
    name = reverse_geocode(lat, lng) or f"Saved place {count + 1}"
    place = Place(user_id=user_id, name=name, lat=lat, lng=lng, geohash=gh.encode(lat, lng, 7),
                  record_count=1, last_visit_at=when, created_at=when)
    db.add(place)
    db.flush()
    return place

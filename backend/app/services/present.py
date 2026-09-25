"""Turning database rows into what the app shows, and into the text the AI reads."""
from datetime import datetime, timedelta

from ..models import Person, Place, Record
from ..security import sign_media


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def local(dt: datetime, tz: int) -> datetime:
    return dt + timedelta(minutes=tz)


def _clock(d: datetime) -> str:
    # Written by hand because strftime("%-I") does not work on Windows.
    h = d.hour % 12 or 12
    return f"{h}:{d.minute:02d} {'AM' if d.hour < 12 else 'PM'}"


def when_long(dt: datetime, tz: int) -> str:
    """'Wednesday 23 September 2026, 9:10 AM' - full words so the guard can match 'Wednesday'."""
    d = local(dt, tz)
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')} {d.year}, {_clock(d)}"


def when_short(dt: datetime, tz: int) -> str:
    d = local(dt, tz)
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')}, {_clock(d)}"


def person_out(p: Person, **extra) -> dict:
    return {"id": p.id, "name": p.name, "relation": p.relation or "", **extra}


def place_out(p: Place, **extra) -> dict:
    return {"id": p.id, "name": p.name, "lat": p.lat, "lng": p.lng, "geohash": p.geohash,
            "record_count": p.record_count, "last_visit_at": iso(p.last_visit_at), **extra}


def record_out(r: Record) -> dict:
    media = r.media
    return {
        "id": r.id,
        "kind": r.kind,
        "text": r.text or "",
        "transcript": r.transcript or "",
        "caption": r.caption or "",
        "display_text": r.display_text,
        "lat": r.lat,
        "lng": r.lng,
        "place": {"id": r.place.id, "name": r.place.name} if r.place else None,
        "people": [person_out(p) for p in r.people],
        "is_private": bool(r.is_private),
        "created_at": iso(r.created_at),
        "added_by_caregiver": bool(r.created_by and r.created_by != r.user_id),
        "media_url": sign_media(media.id) if media else None,
        "media_mime": media.mime if media else None,
    }


def ai_item(r: Record, tz: int) -> dict:
    """One memory as the AI and the GroundingGuard see it."""
    place = r.place.name if r.place else ""
    people = [p.name for p in r.people]
    memory = r.display_text or ("A photo" if r.kind == "photo" else "A voice note")
    context = when_long(r.created_at, tz) + (f" at {place}" if place else "") + ". "
    if people:
        context += "With " + ", ".join(people) + ". "
    context += memory
    return {"id": r.id, "kind": r.kind, "when": when_short(r.created_at, tz), "place": place,
            "people": people, "memory": memory, "context": context}

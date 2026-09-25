import random
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, get_db
from ..domain.text import content_tokens
from ..models import Media, Person, Place, Record, RecordPerson, User
from ..providers.llm import ProviderError, get_provider
from ..security import check_media_signature, current_user, patient_scope, require_patient
from ..services.places import assign_place, places_near
from ..services.present import iso, person_out, place_out, record_out, when_short

router = APIRouter(prefix="/api", tags=["memories"])

ALLOWED_MEDIA = ("image/", "audio/")


def _enrich(record_id: int):
    """After saving: transcribe voice notes and describe photos, when a model is configured."""
    provider = get_provider()
    if provider.name == "offline":
        return
    db = SessionLocal()
    try:
        rec = db.get(Record, record_id)
        if not rec or not rec.media:
            return
        try:
            if rec.kind == "voice" and not rec.transcript:
                rec.transcript = provider.transcribe(rec.media.data, rec.media.mime) or ""
            if rec.kind == "photo" and not rec.caption:
                rec.caption = provider.caption(rec.media.data, rec.media.mime) or ""
            db.commit()
        except ProviderError:
            db.rollback()
    finally:
        db.close()


def _people_for(db: Session, owner_id: int, person_ids: str, new_people: str) -> list[Person]:
    people = []
    ids = [int(x) for x in (person_ids or "").split(",") if x.strip().isdigit()]
    if ids:
        people += db.query(Person).filter(Person.user_id == owner_id, Person.id.in_(ids)).all()
    for name in [n.strip() for n in (new_people or "").split(",") if n.strip()]:
        existing = db.query(Person).filter(Person.user_id == owner_id, func.lower(Person.name) == name.lower()).first()
        if not existing:
            existing = Person(user_id=owner_id, name=name[:120])
            db.add(existing)
            db.flush()
        if existing not in people:
            people.append(existing)
    return people


@router.post("/records")
async def create_record(
    background: BackgroundTasks,
    kind: str = Form("text"),
    text: str = Form(""),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    is_private: bool = Form(False),
    person_ids: str = Form(""),
    new_people: str = Form(""),
    patient_id: int | None = Form(None),
    file: UploadFile | None = File(None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    owner_id, is_owner = patient_scope(db, user, patient_id, "add_memory", "Added a memory")
    if kind not in ("text", "photo", "voice", "message"):
        raise HTTPException(400, "Choose text, photo or voice.")
    if kind == "message":
        # A short note from a family member, shown on the person's Home ("From Anita: ...").
        if is_owner:
            raise HTTPException(400, "Messages are written by family members.")
        if not text.strip():
            raise HTTPException(400, "Write the message first.")
        text = f"Message from {user.name.split()[0]}: {text.strip()}"
    data, mime = None, None
    if file is not None:
        mime = file.content_type or "application/octet-stream"
        if not mime.startswith(ALLOWED_MEDIA):
            raise HTTPException(400, "Only photos and voice recordings can be saved.")
        data = await file.read()
        if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(413, f"That file is larger than {settings.MAX_UPLOAD_MB:g} MB.")
    if not text.strip() and data is None:
        raise HTTPException(400, "Add a few words, a photo or a voice note.")

    now = datetime.utcnow()
    rec = Record(user_id=owner_id, created_by=user.id, kind=kind, text=text.strip()[:2000], lat=lat, lng=lng,
                 is_private=bool(is_private) if is_owner else False, created_at=now)
    if lat is not None and lng is not None:
        rec.place_id = assign_place(db, owner_id, lat, lng, now).id
    db.add(rec)
    db.flush()
    for p in _people_for(db, owner_id, person_ids, new_people):
        db.add(RecordPerson(record_id=rec.id, person_id=p.id))
    if data is not None:
        db.add(Media(record_id=rec.id, user_id=owner_id, mime=mime, size=len(data), data=data))
    db.commit()
    db.refresh(rec)
    background.add_task(_enrich, rec.id)
    return record_out(rec)


@router.get("/records")
def list_records(
    patient_id: int | None = None,
    place_id: int | None = None,
    person_id: int | None = None,
    kind: str = "",
    q: str = "",
    limit: int = Query(60, le=200),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    owner_id, is_owner = patient_scope(db, user, patient_id, "view_memories", "Looked at memories")
    query = db.query(Record).filter(Record.user_id == owner_id, Record.deleted_at.is_(None))
    if not is_owner:
        query = query.filter(Record.is_private.is_(False))
    if place_id:
        query = query.filter(Record.place_id == place_id)
    if person_id:
        query = query.join(RecordPerson, RecordPerson.record_id == Record.id).filter(RecordPerson.person_id == person_id)
    if kind:
        query = query.filter(Record.kind == kind)
    rows = query.order_by(Record.created_at.desc()).limit(500 if q else limit).all()
    if q.strip():
        want = set(content_tokens(q))
        rows = [r for r in rows if want & set(content_tokens(
            " ".join([r.display_text, r.place.name if r.place else ""] + [p.name for p in r.people])))][:limit]
    return [record_out(r) for r in rows]


class RecordPatch(BaseModel):
    text: str | None = None
    is_private: bool | None = None
    person_ids: list[int] | None = None


def _own_record(db: Session, user: User, record_id: int) -> Record:
    rec = db.get(Record, record_id)
    if not rec or rec.deleted_at or rec.user_id != user.id:
        raise HTTPException(404, "Memory not found.")
    return rec


@router.patch("/records/{record_id}")
def update_record(record_id: int, body: RecordPatch, user: User = Depends(require_patient),
                  db: Session = Depends(get_db)):
    rec = _own_record(db, user, record_id)
    if body.text is not None:
        rec.text = body.text.strip()[:2000]
        rec.embedding, rec.embed_model = None, ""
    if body.is_private is not None:
        rec.is_private = body.is_private
    if body.person_ids is not None:
        db.query(RecordPerson).filter(RecordPerson.record_id == rec.id).delete()
        valid = db.query(Person).filter(Person.user_id == user.id, Person.id.in_(body.person_ids or [-1])).all()
        for p in valid:
            db.add(RecordPerson(record_id=rec.id, person_id=p.id))
    db.commit()
    db.refresh(rec)
    return record_out(rec)


@router.delete("/records/{record_id}")
def delete_record(record_id: int, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rec = _own_record(db, user, record_id)
    rec.deleted_at = datetime.utcnow()
    if rec.place and rec.place.record_count:
        rec.place.record_count -= 1
    db.commit()
    return {"deleted": True}


@router.post("/records/{record_id}/restore")
def restore_record(record_id: int, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rec = db.get(Record, record_id)
    if not rec or rec.user_id != user.id or not rec.deleted_at:
        raise HTTPException(404, "Nothing to restore.")
    rec.deleted_at = None
    if rec.place:
        rec.place.record_count = (rec.place.record_count or 0) + 1
    db.commit()
    db.refresh(rec)
    return record_out(rec)


@router.get("/media/{media_id}")
def get_media(media_id: int, exp: int, sig: str, db: Session = Depends(get_db)):
    if not check_media_signature(media_id, exp, sig):
        raise HTTPException(403, "This link has expired. Open the memory again.")
    m = db.get(Media, media_id)
    if not m:
        raise HTTPException(404, "File not found.")
    return Response(content=m.data, media_type=m.mime, headers={"Cache-Control": "private, max-age=3000"})


# ---------------------------------------------------------------- places
@router.get("/places")
def list_places(patient_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owner_id, is_owner = patient_scope(db, user, patient_id, "view_places", "Looked at places")
    counts = db.query(Record.place_id, func.count(Record.id)).filter(
        Record.user_id == owner_id, Record.deleted_at.is_(None), Record.place_id.isnot(None),
        *([] if is_owner else [Record.is_private.is_(False)])).group_by(Record.place_id).all()
    count_map = dict(counts)
    places = db.query(Place).filter(Place.user_id == owner_id).all()
    out = [place_out(p, memory_count=count_map.get(p.id, 0)) for p in places]
    return sorted(out, key=lambda p: p["last_visit_at"] or "", reverse=True)


@router.get("/places/nearby")
def nearby(lat: float, lng: float, tz: int = 330, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    found = places_near(db, user.id, lat, lng, settings.NEARBY_RADIUS_M)
    out = []
    for place, dist in found[:3]:
        recent = (db.query(Record).filter(Record.place_id == place.id, Record.deleted_at.is_(None))
                  .order_by(Record.created_at.desc()).limit(3).all())
        count = db.query(Record).filter(Record.place_id == place.id, Record.deleted_at.is_(None)).count()
        people = sorted({p.name for r in recent for p in r.people})
        out.append(place_out(place, distance_m=round(dist), memory_count=count, people=people,
                             last=[{**record_out(r), "when": when_short(r.created_at, tz)} for r in recent]))
    return out


class PlacePatch(BaseModel):
    name: str


@router.patch("/places/{place_id}")
def rename_place(place_id: int, body: PlacePatch, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    place = db.get(Place, place_id)
    if not place or place.user_id != user.id:
        raise HTTPException(404, "Place not found.")
    if not body.name.strip():
        raise HTTPException(400, "Give the place a name.")
    place.name = body.name.strip()[:200]
    db.commit()
    return place_out(place)


class MergeIn(BaseModel):
    into_id: int


@router.post("/places/{place_id}/merge")
def merge_place(place_id: int, body: MergeIn, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    src, dst = db.get(Place, place_id), db.get(Place, body.into_id)
    if not src or not dst or src.user_id != user.id or dst.user_id != user.id or src.id == dst.id:
        raise HTTPException(400, "Choose two different places of yours.")
    db.query(Record).filter(Record.place_id == src.id).update({Record.place_id: dst.id})
    dst.record_count = (dst.record_count or 0) + (src.record_count or 0)
    dst.last_visit_at = max(dst.last_visit_at, src.last_visit_at)
    db.delete(src)
    db.commit()
    return place_out(dst)


# ---------------------------------------------------------------- people
class PersonIn(BaseModel):
    name: str
    relation: str = ""


@router.get("/people")
def list_people(patient_id: int | None = None, tz: int = 330, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    owner_id, is_owner = patient_scope(db, user, patient_id, "view_people", "Looked at people")
    people = db.query(Person).filter(Person.user_id == owner_id).order_by(Person.name).all()
    out = []
    for p in people:
        q = (db.query(Record).join(RecordPerson, RecordPerson.record_id == Record.id)
             .filter(RecordPerson.person_id == p.id, Record.deleted_at.is_(None)))
        if not is_owner:
            q = q.filter(Record.is_private.is_(False))
        last = q.order_by(Record.created_at.desc()).first()
        out.append(person_out(p, memory_count=q.count(), last_seen=iso(last.created_at) if last else None,
                              last_text=last.display_text if last else "",
                              last_place=last.place.name if last and last.place else ""))
    return out


@router.post("/people")
def add_person(body: PersonIn, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    if not body.name.strip():
        raise HTTPException(400, "Write the person's name.")
    p = Person(user_id=user.id, name=body.name.strip()[:120], relation=body.relation.strip()[:80])
    db.add(p)
    db.commit()
    return person_out(p, memory_count=0, last_seen=None, last_text="", last_place="")


@router.patch("/people/{person_id}")
def edit_person(person_id: int, body: PersonIn, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    p = db.get(Person, person_id)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Person not found.")
    p.name, p.relation = body.name.strip()[:120] or p.name, body.relation.strip()[:80]
    db.commit()
    return person_out(p)


@router.delete("/people/{person_id}")
def remove_person(person_id: int, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    p = db.get(Person, person_id)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Person not found.")
    db.query(RecordPerson).filter(RecordPerson.person_id == p.id).delete()
    db.delete(p)
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------- memory practice
@router.get("/practice")
def practice(tz: int = 330, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    """A gentle recall exercise: show a cue (place, day, photo), let the person think, then reveal."""
    pool = (db.query(Record).filter(Record.user_id == user.id, Record.deleted_at.is_(None),
                                    Record.is_private.is_(False), Record.kind != "log")
            .order_by(Record.created_at.desc()).limit(40).all())
    pool = [r for r in pool if r.place or r.people]
    if not pool:
        return None
    r = random.choice(pool)
    when = when_short(r.created_at, tz).split(",")[0]
    if r.people and r.place:
        prompt = f"On {when} you were at {r.place.name}. Who was with you?"
    elif r.people:
        prompt = f"On {when}, who were you with?"
    else:
        prompt = f"What happened at {r.place.name} on {when}?"
    return {"prompt": prompt, "memory": record_out(r)}

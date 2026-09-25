import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AccessLog, Alert, CareLink, LinkCode, QueryLog, Record, Reminder, ReminderEvent, User
from ..security import active_link, current_user, patient_scope, require_caregiver, require_patient
from ..services.present import iso, record_out

router = APIRouter(prefix="/api", tags=["care"])


def _local_today(tz: int) -> tuple[str, str]:
    now_local = datetime.utcnow() + timedelta(minutes=tz)
    return now_local.strftime("%Y-%m-%d"), now_local.strftime("%H:%M")


def _link_out(link: CareLink, viewer: User) -> dict:
    other = link.caregiver if viewer.role == "patient" else link.patient
    return {"id": link.id, "person": {"id": other.id, "name": other.name, "phone": other.phone or ""},
            "created_at": iso(link.created_at), "revoked_at": iso(link.revoked_at), "active": link.revoked_at is None}


# ---------------------------------------------------------------- linking
@router.post("/care/code")
def new_code(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    code = f"{secrets.randbelow(900000) + 100000}"
    db.add(LinkCode(code=code, patient_id=user.id, expires_at=datetime.utcnow() + timedelta(hours=24)))
    db.commit()
    return {"code": code, "expires_at": iso(datetime.utcnow() + timedelta(hours=24))}


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


@router.post("/care/link")
def use_code(body: CodeIn, user: User = Depends(require_caregiver), db: Session = Depends(get_db)):
    lc = db.get(LinkCode, body.code.strip())
    if not lc or lc.used_at or lc.expires_at < datetime.utcnow():
        raise HTTPException(400, "This code is wrong or has expired. Ask for a new code.")
    if active_link(db, lc.patient_id, user.id):
        raise HTTPException(409, "You are already linked to this person.")
    lc.used_at = datetime.utcnow()
    link = CareLink(patient_id=lc.patient_id, caregiver_id=user.id)
    db.add(link)
    db.add(AccessLog(patient_id=lc.patient_id, actor_id=user.id, action="linked", detail="Joined as caregiver"))
    db.commit()
    db.refresh(link)
    return _link_out(link, user)


@router.get("/care/links")
def links(user: User = Depends(current_user), db: Session = Depends(get_db)):
    col = CareLink.patient_id if user.role == "patient" else CareLink.caregiver_id
    rows = db.query(CareLink).filter(col == user.id).order_by(CareLink.created_at.desc()).all()
    if user.role == "caregiver":
        rows = [r for r in rows if r.revoked_at is None]
    return [_link_out(r, user) for r in rows]


@router.post("/care/links/{link_id}/revoke")
def revoke(link_id: int, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    link = db.get(CareLink, link_id)
    if not link or link.patient_id != user.id:
        raise HTTPException(404, "Link not found.")
    if link.revoked_at is None:
        link.revoked_at = datetime.utcnow()  # never deleted: the audit trail keeps it
        db.add(AccessLog(patient_id=user.id, actor_id=user.id, action="revoked",
                         detail=f"Removed access for {link.caregiver.name}"))
        db.commit()
    return _link_out(link, user)


# ---------------------------------------------------------------- reminders
def _reminders_today(db: Session, patient_id: int, tz: int) -> list[dict]:
    today, hhmm = _local_today(tz)
    rems = (db.query(Reminder).filter(Reminder.user_id == patient_id, Reminder.active.is_(True))
            .order_by(Reminder.time_hhmm).all())
    done = {e.reminder_id: e for e in db.query(ReminderEvent).filter(ReminderEvent.user_id == patient_id,
                                                                     ReminderEvent.local_date == today)}
    out = []
    for r in rems:
        ev = done.get(r.id)
        status = "done" if ev else ("due" if r.time_hhmm <= hhmm else "later")
        out.append({"id": r.id, "title": r.title, "time": r.time_hhmm, "status": status,
                    "done_at": iso(ev.done_at) if ev else None})
    return out


class ReminderIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    patient_id: int | None = None


@router.get("/reminders")
def list_reminders(patient_id: int | None = None, tz: int = 330, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    owner_id, _ = patient_scope(db, user, patient_id, "view_reminders", "Looked at reminders")
    return _reminders_today(db, owner_id, tz)


@router.post("/reminders")
def add_reminder(body: ReminderIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owner_id, _ = patient_scope(db, user, body.patient_id, "add_reminder", f"Added reminder '{body.title}'")
    db.add(Reminder(user_id=owner_id, title=body.title.strip(), time_hhmm=body.time, created_by=user.id))
    db.commit()
    return {"ok": True}


@router.delete("/reminders/{rid}")
def delete_reminder(rid: int, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    r = db.get(Reminder, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Reminder not found.")
    r.active = False
    db.commit()
    return {"ok": True}


@router.post("/reminders/{rid}/done")
def mark_done(rid: int, tz: int = 330, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    """Also saves a log memory, so later "Did I take my morning tablet?" has a real answer."""
    r = db.get(Reminder, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Reminder not found.")
    today, _ = _local_today(tz)
    exists = db.query(ReminderEvent).filter(ReminderEvent.reminder_id == r.id, ReminderEvent.local_date == today).first()
    if not exists:
        db.add(ReminderEvent(reminder_id=r.id, user_id=user.id, local_date=today))
        db.add(Record(user_id=user.id, created_by=user.id, kind="log", text=f"Marked '{r.title}' as done."))
        db.commit()
    return _reminders_today(db, user.id, tz)


# ---------------------------------------------------------------- SOS
class SosIn(BaseModel):
    lat: float | None = None
    lng: float | None = None


@router.post("/sos")
def sos(body: SosIn, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    alert = Alert(patient_id=user.id, lat=body.lat, lng=body.lng)
    db.add(alert)
    db.commit()
    carers = [{"name": l.caregiver.name, "phone": l.caregiver.phone or ""}
              for l in db.query(CareLink).filter(CareLink.patient_id == user.id, CareLink.revoked_at.is_(None))]
    return {"id": alert.id, "created_at": iso(alert.created_at), "caregivers": carers}


@router.get("/alerts")
def alerts(patient_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owner_id, _ = patient_scope(db, user, patient_id, "view_alerts", "Checked alerts")
    rows = db.query(Alert).filter(Alert.patient_id == owner_id).order_by(Alert.created_at.desc()).limit(20).all()
    return [{"id": a.id, "lat": a.lat, "lng": a.lng, "created_at": iso(a.created_at),
             "resolved_at": iso(a.resolved_at)} for a in rows]


@router.post("/alerts/{alert_id}/resolve")
def resolve(alert_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found.")
    patient_scope(db, user, a.patient_id, "resolve_alert", "Marked an SOS as handled")
    a.resolved_at, a.resolved_by = datetime.utcnow(), user.id
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- caregiver dashboard
@router.get("/care/dashboard/{patient_id}")
def dashboard(patient_id: int, tz: int = 330, user: User = Depends(require_caregiver), db: Session = Depends(get_db)):
    pid, _ = patient_scope(db, user, patient_id, "view_dashboard", "Opened the dashboard")
    patient = db.get(User, pid)
    today, _ = _local_today(tz)
    start_utc = datetime.strptime(today, "%Y-%m-%d") - timedelta(minutes=tz)
    visible = db.query(Record).filter(Record.user_id == pid, Record.deleted_at.is_(None), Record.is_private.is_(False),
                                      Record.kind != "message")
    recent = visible.order_by(Record.created_at.desc()).limit(8).all()
    last_any = (db.query(Record).filter(Record.user_id == pid, Record.deleted_at.is_(None))
                .order_by(Record.created_at.desc()).first())
    open_alerts = db.query(Alert).filter(Alert.patient_id == pid, Alert.resolved_at.is_(None)).all()
    # Memories saved per day for the last 7 days (local days), oldest first, for the activity chart.
    week_start = start_utc - timedelta(days=6)
    counts = {}
    for (created,) in db.query(Record.created_at).filter(Record.user_id == pid, Record.deleted_at.is_(None),
                                                         Record.created_at >= week_start, Record.kind != "message"):
        day = (created + timedelta(minutes=tz)).strftime("%Y-%m-%d")
        counts[day] = counts.get(day, 0) + 1
    week = []
    for i in range(7):
        d = datetime.strptime(today, "%Y-%m-%d") - timedelta(days=6 - i)
        key = d.strftime("%Y-%m-%d")
        week.append({"date": key, "label": d.strftime("%a"), "count": counts.get(key, 0)})
    messages = (db.query(Record).filter(Record.user_id == pid, Record.deleted_at.is_(None), Record.kind == "message")
                .order_by(Record.created_at.desc()).limit(5).all())
    return {
        "week": week,
        "messages": [record_out(r) for r in messages],
        "patient": {"id": patient.id, "name": patient.name},
        "today": {
            "memories": visible.filter(Record.created_at >= start_utc).count(),
            "questions": db.query(QueryLog).filter(QueryLog.user_id == pid, QueryLog.source == "app",
                                                   QueryLog.created_at >= start_utc).count(),
            "last_active": iso(last_any.created_at) if last_any else None,
        },
        "reminders": _reminders_today(db, pid, tz),
        "alerts": [{"id": a.id, "lat": a.lat, "lng": a.lng, "created_at": iso(a.created_at)} for a in open_alerts],
        "recent": [record_out(r) for r in recent],
    }


# ---------------------------------------------------------------- who saw my data
@router.get("/privacy/log")
def privacy_log(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rows = (db.query(AccessLog).filter(AccessLog.patient_id == user.id)
            .order_by(AccessLog.created_at.desc()).limit(80).all())
    private_count = db.query(Record).filter(Record.user_id == user.id, Record.is_private.is_(True),
                                            Record.deleted_at.is_(None)).count()
    questions = db.query(QueryLog).filter(QueryLog.user_id == user.id, QueryLog.source == "app").count()
    return {
        "events": [{"id": r.id, "who": r.actor.name if r.actor_id != user.id else "You", "action": r.action,
                    "detail": r.detail, "at": iso(r.created_at)} for r in rows],
        "private_memories": private_count,
        "questions_asked": questions,
    }

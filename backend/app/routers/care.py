import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import AccessLog, Alert, CareLink, LinkCode, QueryLog, Record, Reminder, ReminderEvent, User
from ..security import (PERMISSIONS, active_link, can_manage, check_reminder_voice, clean_permissions, current_user,
                        link_permissions, patient_scope, primary_link, require_caregiver, require_patient,
                        sign_reminder_voice)
from ..services.present import iso, record_out
from ..services.privacy import build_redactor

router = APIRouter(prefix="/api", tags=["care"])

REMINDER_KINDS = ("medication", "activity", "appointment", "other")


def _local_today(tz: int) -> tuple[str, str]:
    now_local = datetime.utcnow() + timedelta(minutes=tz)
    return now_local.strftime("%Y-%m-%d"), now_local.strftime("%H:%M")


def _audit(db: Session, patient_id: int, actor_id: int, action: str, detail: str):
    db.add(AccessLog(patient_id=patient_id, actor_id=actor_id, action=action, detail=detail[:300]))


def _link_out(link: CareLink, viewer: User) -> dict:
    other = link.caregiver if viewer.role == "patient" else link.patient
    return {"id": link.id, "person": {"id": other.id, "name": other.name, "phone": other.phone or ""},
            "role": link.role, "relation": link.relation or "", "permissions": link_permissions(link),
            "created_at": iso(link.created_at), "revoked_at": iso(link.revoked_at), "active": link.revoked_at is None}


def _new_code(db: Session, patient_id: int, issued_by: int, role: str, permissions: dict | None, label: str) -> LinkCode:
    for _ in range(20):
        code = f"{secrets.randbelow(900000) + 100000}"
        if not db.get(LinkCode, code):
            break
    lc = LinkCode(code=code, patient_id=patient_id, issued_by=issued_by, link_role=role, permissions=permissions,
                  label=label[:60], expires_at=datetime.utcnow() + timedelta(hours=24))
    db.add(lc)
    return lc


# ---------------------------------------------------------------- linking
@router.post("/care/code")
def new_code(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    """The person makes a code. The first caregiver to join becomes the primary caregiver."""
    role = "secondary" if primary_link(db, user.id) else "primary"
    lc = _new_code(db, user.id, user.id, role, None, "")
    db.commit()
    return {"code": lc.code, "expires_at": iso(lc.expires_at), "role": role}


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


@router.post("/care/link")
def use_code(body: CodeIn, user: User = Depends(require_caregiver), db: Session = Depends(get_db)):
    lc = db.get(LinkCode, body.code.strip())
    if not lc or lc.used_at or lc.expires_at < datetime.utcnow():
        raise HTTPException(400, "This code is wrong or has expired. Ask for a new code.")
    if active_link(db, lc.patient_id, user.id):
        raise HTTPException(409, "You are already linked to this person.")
    role = lc.link_role or "secondary"
    if role == "primary" and primary_link(db, lc.patient_id):
        role = "secondary"  # someone joined first with an earlier code
    if not primary_link(db, lc.patient_id) and not lc.link_role:
        role = "primary"
    lc.used_at = datetime.utcnow()
    link = CareLink(patient_id=lc.patient_id, caregiver_id=user.id, role=role,
                    permissions=None if role == "primary" else clean_permissions(lc.permissions),
                    relation=lc.label or "", invited_by=lc.issued_by)
    db.add(link)
    _audit(db, lc.patient_id, user.id, "linked", "Joined as the primary caregiver" if role == "primary" else "Joined as a caregiver")
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


# ---------------------------------------------------------------- care team (primary caregiver manages the others)
def _team_out(db: Session, patient_id: int, viewer: User) -> dict:
    manage = can_manage(db, viewer, patient_id)
    links = (db.query(CareLink).filter(CareLink.patient_id == patient_id, CareLink.revoked_at.is_(None))
             .order_by(CareLink.role.desc(), CareLink.created_at).all())   # "secondary" > "primary": primary first
    links.sort(key=lambda l: (l.role != "primary", l.created_at))
    members = [{"link_id": l.id, "name": l.caregiver.name, "phone": l.caregiver.phone or "", "role": l.role,
                "relation": l.relation or "", "permissions": link_permissions(l), "since": iso(l.created_at),
                "is_you": l.caregiver_id == viewer.id} for l in links]
    if not manage:   # a secondary caregiver sees the team, but not other people's permissions
        members = [m if m["is_you"] else {**m, "permissions": None, "phone": ""} for m in members]
    invites = []
    if manage:
        now = datetime.utcnow()
        for c in (db.query(LinkCode).filter(LinkCode.patient_id == patient_id, LinkCode.used_at.is_(None),
                                            LinkCode.expires_at > now).order_by(LinkCode.expires_at.desc())):
            invites.append({"code": c.code, "label": c.label or "", "role": c.link_role or "secondary",
                            "permissions": None if c.link_role == "primary" else clean_permissions(c.permissions),
                            "expires_at": iso(c.expires_at)})
    patient = db.get(User, patient_id)
    return {"patient": {"id": patient.id, "name": patient.name}, "can_manage": manage, "members": members,
            "invites": invites, "catalog": PERMISSIONS}


def _team_patient(db: Session, user: User, patient_id: int) -> int:
    if user.role == "patient":
        if patient_id != user.id:
            raise HTTPException(403, "You can only manage your own family.")
        return user.id
    if not active_link(db, patient_id, user.id):
        raise HTTPException(403, "You are not linked to this person, or they removed your access.")
    return patient_id


@router.get("/care/team/{patient_id}")
def team(patient_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    pid = _team_patient(db, user, patient_id)
    return _team_out(db, pid, user)


class InviteIn(BaseModel):
    label: str = Field(default="", max_length=60)
    permissions: dict = Field(default_factory=dict)


@router.post("/care/team/{patient_id}/invite")
def invite(patient_id: int, body: InviteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    pid = _team_patient(db, user, patient_id)
    if not can_manage(db, user, pid):
        raise HTTPException(403, "Only the primary caregiver can invite other caregivers.")
    role = "secondary" if primary_link(db, pid) else "primary"
    perms = clean_permissions(body.permissions)
    lc = _new_code(db, pid, user.id, role, None if role == "primary" else perms, body.label.strip())
    who = body.label.strip() or "a caregiver"
    _audit(db, pid, user.id, "invited", f"Invited {who}")
    db.commit()
    return {"code": lc.code, "expires_at": iso(lc.expires_at), "role": role,
            "permissions": None if role == "primary" else perms, "label": lc.label}


@router.post("/care/codes/{code}/cancel")
def cancel_invite(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lc = db.get(LinkCode, code)
    if not lc or lc.used_at:
        raise HTTPException(404, "Invitation not found.")
    if not can_manage(db, user, lc.patient_id):
        raise HTTPException(403, "Only the primary caregiver can cancel invitations.")
    lc.expires_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


class LinkPatch(BaseModel):
    permissions: dict | None = None
    relation: str | None = Field(default=None, max_length=60)


@router.patch("/care/links/{link_id}")
def update_link(link_id: int, body: LinkPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    link = db.get(CareLink, link_id)
    if not link or link.revoked_at is not None:
        raise HTTPException(404, "Caregiver not found.")
    if not can_manage(db, user, link.patient_id):
        raise HTTPException(403, "Only the primary caregiver can change what others see.")
    if body.permissions is not None:
        if link.role == "primary":
            raise HTTPException(400, "The primary caregiver always sees everything.")
        before = link_permissions(link)
        link.permissions = clean_permissions(body.permissions)
        changed = [PERMISSIONS[k].split(",")[0] + (" on" if v else " off")
                   for k, v in link.permissions.items() if before.get(k) != v]
        _audit(db, link.patient_id, user.id, "permissions_changed",
               f"Changed {link.caregiver.name}'s access" + (f": {'; '.join(changed)}" if changed else ""))
    if body.relation is not None:
        link.relation = body.relation.strip()
    db.commit()
    db.refresh(link)
    return _team_out(db, link.patient_id, user)


@router.post("/care/links/{link_id}/make-primary")
def make_primary(link_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    link = db.get(CareLink, link_id)
    if not link or link.revoked_at is not None:
        raise HTTPException(404, "Caregiver not found.")
    if not can_manage(db, user, link.patient_id):
        raise HTTPException(403, "Only the person or the primary caregiver can choose the primary caregiver.")
    current = primary_link(db, link.patient_id)
    if current and current.id != link.id:
        current.role = "secondary"
        current.permissions = {k: True for k in PERMISSIONS}  # keeps what they could see; can be reduced later
    link.role = "primary"
    link.permissions = None
    _audit(db, link.patient_id, user.id, "made_primary", f"{link.caregiver.name} is now the primary caregiver")
    db.commit()
    return _team_out(db, link.patient_id, user)


@router.post("/care/links/{link_id}/revoke")
def revoke(link_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The person can remove anyone; the primary caregiver can remove other caregivers; anyone can leave."""
    link = db.get(CareLink, link_id)
    if not link:
        raise HTTPException(404, "Link not found.")
    is_self = link.caregiver_id == user.id
    if user.role == "patient":
        if link.patient_id != user.id:
            raise HTTPException(404, "Link not found.")
    elif not is_self:
        if not can_manage(db, user, link.patient_id):
            raise HTTPException(403, "Only the primary caregiver can remove other caregivers.")
    if link.revoked_at is None:
        link.revoked_at = datetime.utcnow()  # never deleted: the audit trail keeps it
        if is_self:
            _audit(db, link.patient_id, user.id, "left", f"{user.name} stopped being a caregiver")
        else:
            _audit(db, link.patient_id, user.id, "revoked", f"Removed access for {link.caregiver.name}")
        db.commit()
    return _link_out(link, user)


# ---------------------------------------------------------------- reminders
def _reminder_out(r: Reminder, status: str, ev) -> dict:
    return {"id": r.id, "title": r.title, "time": r.time_hhmm, "kind": r.kind or "other", "note": r.note or "",
            "repeat": r.repeat_mode or "daily", "on_date": r.on_date, "speak": r.speak is not False,
            "status": status, "done_at": iso(ev.done_at) if ev else None,
            "voice_url": sign_reminder_voice(r.id) if r.voice_mime else None}


def _reminders(db: Session, patient_id: int, tz: int, scope: str = "today") -> list[dict]:
    today, hhmm = _local_today(tz)
    rems = (db.query(Reminder).filter(Reminder.user_id == patient_id, Reminder.active.is_(True))
            .order_by(Reminder.time_hhmm).all())
    done = {e.reminder_id: e for e in db.query(ReminderEvent).filter(ReminderEvent.user_id == patient_id,
                                                                     ReminderEvent.local_date == today)}
    out = []
    for r in rems:
        once = (r.repeat_mode or "daily") == "once"
        if once and r.on_date and r.on_date < today:
            continue                                    # past one-time reminders drop off
        if once and r.on_date != today:
            if scope == "all":
                out.append(_reminder_out(r, "upcoming", None))
            continue
        ev = done.get(r.id)
        status = "done" if ev else ("due" if r.time_hhmm <= hhmm else "later")
        out.append(_reminder_out(r, status, ev))
    out.sort(key=lambda x: ((x["on_date"] or today), x["time"]))
    return out


def _reminders_today(db: Session, patient_id: int, tz: int) -> list[dict]:
    return _reminders(db, patient_id, tz, "today")


class ReminderIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    kind: str = "other"
    note: str = Field(default="", max_length=300)
    repeat: str = Field(default="daily", pattern="^(daily|once)$")
    on_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    speak: bool = True
    patient_id: int | None = None


def _own_reminder(db: Session, user: User, rid: int, action: str, detail: str) -> Reminder:
    r = db.get(Reminder, rid)
    if not r or not r.active:
        raise HTTPException(404, "Reminder not found.")
    patient_scope(db, user, r.user_id, action, detail, perm="reminders")
    return r


@router.get("/reminders")
def list_reminders(patient_id: int | None = None, tz: int = 330, scope: str = "today",
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    owner_id, _ = patient_scope(db, user, patient_id, "view_reminders", "Looked at reminders", perm="reminders")
    return _reminders(db, owner_id, tz, "all" if scope == "all" else "today")


@router.post("/reminders")
def add_reminder(body: ReminderIn, tz: int = 330, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owner_id, _ = patient_scope(db, user, body.patient_id, "add_reminder", f"Added reminder '{body.title}'",
                                perm="reminders")
    if body.kind not in REMINDER_KINDS:
        raise HTTPException(400, "Choose medicine, activity, appointment or other.")
    if body.repeat == "once" and not body.on_date:
        raise HTTPException(400, "Choose the date for a one-time reminder.")
    if body.repeat == "once" and body.on_date < _local_today(tz)[0]:
        raise HTTPException(400, "That date has already passed.")
    r = Reminder(user_id=owner_id, title=body.title.strip(), time_hhmm=body.time, kind=body.kind,
                 note=body.note.strip(), repeat_mode=body.repeat, on_date=body.on_date if body.repeat == "once" else None,
                 speak=body.speak, created_by=user.id)
    db.add(r)
    db.commit()
    return {"ok": True, "id": r.id}


@router.delete("/reminders/{rid}")
def delete_reminder(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _own_reminder(db, user, rid, "remove_reminder", "Removed a reminder")
    r.active = False
    db.commit()
    return {"ok": True}


@router.post("/reminders/{rid}/voice")
async def upload_voice(rid: int, file: UploadFile = File(...), user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    """A recorded voice message that plays when the reminder is due (for example a daughter's voice)."""
    r = _own_reminder(db, user, rid, "add_reminder_voice", "Recorded a voice reminder")
    mime = file.content_type or ""
    if not mime.startswith("audio/"):
        raise HTTPException(400, "Record a voice message.")
    data = await file.read()
    if len(data) > min(settings.MAX_UPLOAD_MB, 4) * 1024 * 1024:
        raise HTTPException(413, "That recording is too long. Keep it under a minute.")
    r.voice_data, r.voice_mime = data, mime
    db.commit()
    return {"ok": True, "voice_url": sign_reminder_voice(r.id)}


@router.delete("/reminders/{rid}/voice")
def delete_voice(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _own_reminder(db, user, rid, "add_reminder_voice", "Removed a voice reminder")
    r.voice_data, r.voice_mime = None, ""
    db.commit()
    return {"ok": True}


@router.get("/reminders/{rid}/voice")
def get_voice(rid: int, exp: int, sig: str, db: Session = Depends(get_db)):
    if not check_reminder_voice(rid, exp, sig):
        raise HTTPException(403, "This link has expired. Open the reminder again.")
    r = db.get(Reminder, rid)
    if not r or not r.voice_mime or r.voice_data is None:
        raise HTTPException(404, "No voice message for this reminder.")
    return Response(content=r.voice_data, media_type=r.voice_mime, headers={"Cache-Control": "private, max-age=3000"})


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
    links = db.query(CareLink).filter(CareLink.patient_id == user.id, CareLink.revoked_at.is_(None)).all()
    links.sort(key=lambda l: l.role != "primary")       # the primary caregiver is called first
    carers = [{"name": l.caregiver.name, "phone": l.caregiver.phone or ""} for l in links if link_permissions(l)["alerts"]]
    return {"id": alert.id, "created_at": iso(alert.created_at), "caregivers": carers}


def _alert_out(a: Alert, show_location: bool) -> dict:
    return {"id": a.id, "lat": a.lat if show_location else None, "lng": a.lng if show_location else None,
            "location_hidden": (not show_location) and a.lat is not None,
            "created_at": iso(a.created_at), "resolved_at": iso(a.resolved_at)}


@router.get("/alerts")
def alerts(patient_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owner_id, is_owner = patient_scope(db, user, patient_id, "view_alerts", "Checked alerts", perm="alerts")
    show_loc = is_owner or link_permissions(active_link(db, owner_id, user.id))["places"]
    rows = db.query(Alert).filter(Alert.patient_id == owner_id).order_by(Alert.created_at.desc()).limit(20).all()
    return [_alert_out(a, show_loc) for a in rows]


@router.post("/alerts/{alert_id}/resolve")
def resolve(alert_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found.")
    patient_scope(db, user, a.patient_id, "resolve_alert", "Marked an SOS as handled", perm="alerts")
    a.resolved_at, a.resolved_by = datetime.utcnow(), user.id
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- caregiver dashboard
@router.get("/care/dashboard/{patient_id}")
def dashboard(patient_id: int, tz: int = 330, user: User = Depends(require_caregiver), db: Session = Depends(get_db)):
    pid, _ = patient_scope(db, user, patient_id, "view_dashboard", "Opened the dashboard")
    link = active_link(db, pid, user.id)
    perms = link_permissions(link)
    patient = db.get(User, pid)
    today, _ = _local_today(tz)
    start_utc = datetime.strptime(today, "%Y-%m-%d") - timedelta(minutes=tz)
    out = {"patient": {"id": patient.id, "name": patient.name},
           "access": {"role": link.role, "permissions": perms, "can_manage": link.role == "primary"},
           "week": None, "messages": None, "today": None, "reminders": None, "alerts": None, "recent": None}
    if perms["memories"]:
        visible = db.query(Record).filter(Record.user_id == pid, Record.deleted_at.is_(None), Record.is_private.is_(False),
                                          Record.kind != "message")
        last_any = (db.query(Record).filter(Record.user_id == pid, Record.deleted_at.is_(None))
                    .order_by(Record.created_at.desc()).first())
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
        out["week"] = week
        out["recent"] = [record_out(r) for r in visible.order_by(Record.created_at.desc()).limit(8).all()]
        out["today"] = {
            "memories": visible.filter(Record.created_at >= start_utc).count(),
            "questions": db.query(QueryLog).filter(QueryLog.user_id == pid, QueryLog.source == "app",
                                                   QueryLog.created_at >= start_utc).count(),
            "last_active": iso(last_any.created_at) if last_any else None,
        }
    if perms["messages"]:
        msgs = (db.query(Record).filter(Record.user_id == pid, Record.deleted_at.is_(None), Record.kind == "message")
                .order_by(Record.created_at.desc()).limit(5).all())
        out["messages"] = [record_out(r) for r in msgs]
    if perms["reminders"]:
        out["reminders"] = _reminders(db, pid, tz, "all")
    if perms["alerts"]:
        open_alerts = db.query(Alert).filter(Alert.patient_id == pid, Alert.resolved_at.is_(None)).all()
        out["alerts"] = [_alert_out(a, perms["places"]) for a in open_alerts]
    return out


# ---------------------------------------------------------------- who saw my data, and what the AI sees
@router.get("/privacy/log")
def privacy_log(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rows = (db.query(AccessLog).filter(AccessLog.patient_id == user.id)
            .order_by(AccessLog.created_at.desc()).limit(80).all())
    private_count = db.query(Record).filter(Record.user_id == user.id, Record.is_private.is_(True),
                                            Record.deleted_at.is_(None)).count()
    questions = db.query(QueryLog).filter(QueryLog.user_id == user.id, QueryLog.source == "app").count()
    ai_sent = db.query(QueryLog).filter(QueryLog.user_id == user.id, QueryLog.source == "app",
                                        QueryLog.ai_payload.isnot(None)).count()
    return {
        "events": [{"id": r.id, "who": r.actor.name if r.actor_id != user.id else "You", "action": r.action,
                    "detail": r.detail, "at": iso(r.created_at)} for r in rows],
        "private_memories": private_count,
        "questions_asked": questions,
        "questions_sent_to_ai": ai_sent,
        "ai_media_consent": bool(user.ai_media_consent),
    }


class PreviewIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.post("/privacy/preview")
def privacy_preview(body: PreviewIn, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    """Shows the person exactly what an external AI would receive for a piece of text."""
    red = build_redactor(db, user)
    sent = red.redact(body.text)
    return {"original": body.text, "sent_to_ai": sent, "hidden": red.replacements()}

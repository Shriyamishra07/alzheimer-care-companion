"""Authentication and authorisation.

Deny by default: every data route calls `patient_scope`, which only lets a
patient see their own data, and a caregiver see a patient's data while an
un-revoked CareLink exists. Every caregiver read is written to AccessLog so the
patient can see it on the "Who saw my data" screen.
"""
import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import AccessLog, CareLink, User

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return "pbkdf2$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, dk_b64 = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), 200_000)
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except Exception:
        return False


def create_token(user: User) -> str:
    payload = {"sub": str(user.id), "role": user.role, "exp": datetime.utcnow() + timedelta(days=settings.TOKEN_DAYS)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    try:
        payload = jwt.decode(creds.credentials, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has ended. Please sign in again.")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found.")
    return user


def require_patient(user: User = Depends(current_user)) -> User:
    if user.role != "patient":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the person who owns these memories can do this.")
    return user


def require_caregiver(user: User = Depends(current_user)) -> User:
    if user.role != "caregiver":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is for caregivers.")
    return user


def active_link(db: Session, patient_id: int, caregiver_id: int):
    return (
        db.query(CareLink)
        .filter(CareLink.patient_id == patient_id, CareLink.caregiver_id == caregiver_id, CareLink.revoked_at.is_(None))
        .first()
    )


def patient_scope(db: Session, user: User, patient_id: int | None, action: str, detail: str = "") -> tuple[int, bool]:
    """Return (patient_id, is_owner). Raises 403 unless the caller may read this patient's data."""
    if user.role == "patient":
        if patient_id not in (None, user.id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only see your own memories.")
        return user.id, True
    if patient_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose which person you care for.")
    if not active_link(db, patient_id, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not linked to this person, or they removed your access.")
    # One audit line per caregiver action per 10 minutes, so auto-refresh doesn't flood the log.
    recent = (db.query(AccessLog)
              .filter(AccessLog.patient_id == patient_id, AccessLog.actor_id == user.id, AccessLog.action == action,
                      AccessLog.created_at >= datetime.utcnow() - timedelta(minutes=10))
              .first())
    if not recent:
        db.add(AccessLog(patient_id=patient_id, actor_id=user.id, action=action, detail=detail[:300]))
        db.commit()
    return patient_id, False


def sign_media(media_id: int) -> str:
    exp = int(time.time()) + settings.MEDIA_URL_SECONDS
    msg = f"{media_id}:{exp}".encode()
    sig = hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]
    return f"/api/media/{media_id}?exp={exp}&sig={sig}"


def check_media_signature(media_id: int, exp: int, sig: str) -> bool:
    if exp < int(time.time()):
        return False
    msg = f"{media_id}:{exp}".encode()
    good = hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(good, sig)

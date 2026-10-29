from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=6, max_length=200)
    role: str = Field(pattern="^(patient|caregiver)$")
    phone: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    ai_media_consent: bool | None = None


def user_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "phone": u.phone or "",
            "ai_media_consent": bool(u.ai_media_consent)}


@router.post("/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    user = User(name=body.name.strip(), email=email, password_hash=hash_password(body.password), role=body.role,
                phone=body.phone.strip())
    db.add(user)
    db.commit()
    return {"token": create_token(user), "user": user_out(user)}


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.strip().lower(), User.is_system.is_(False)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "That email and password don't match. Check them and try again.")
    return {"token": create_token(user), "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.patch("/me")
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name is not None and body.name.strip():
        user.name = body.name.strip()
    if body.phone is not None:
        user.phone = body.phone.strip()
    if body.ai_media_consent is not None:
        if user.role != "patient":
            raise HTTPException(403, "Only the person can choose how the AI handles their photos and voice.")
        user.ai_media_consent = body.ai_media_consent
    db.commit()
    return user_out(user)

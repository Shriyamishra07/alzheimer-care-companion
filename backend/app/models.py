"""Data model. User is the ownership hub: every row points back to the patient who owns it.

Design decisions carried over from Review I:
  * Place.geohash      -> "places near me" is a prefix query, not a full scan
  * QueryLog           -> the measurement instrument for NFR-AI-1..6, not a debug table
  * CareLink.revoked_at -> revocation leaves a trace; links are never deleted
  * Record.is_private  -> enforced on the server, excluded from caregivers and from AI retrieval
"""
from datetime import datetime

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(300), nullable=False)
    role = Column(String(20), nullable=False)  # patient | caregiver
    phone = Column(String(30), default="")
    is_system = Column(Boolean, default=False)  # evaluation personas; hidden from normal login
    created_at = Column(DateTime, default=utcnow)


class Place(Base):
    __tablename__ = "places"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String(200), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    geohash = Column(String(12), index=True, nullable=False)
    record_count = Column(Integer, default=0)  # denormalised so "N memories here" needs no count query
    last_visit_at = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)


class Record(Base):
    __tablename__ = "records"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    kind = Column(String(10), nullable=False)  # text | photo | voice | log
    text = Column(Text, default="")  # what the person typed or said
    transcript = Column(Text, default="")  # voice note transcription (AI, when available)
    caption = Column(Text, default="")  # photo description (AI, when available)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    place_id = Column(Integer, ForeignKey("places.id"), nullable=True, index=True)
    is_private = Column(Boolean, default=False, nullable=False)
    embedding = Column(JSON, nullable=True)  # cached vector for the current embedding model
    embed_model = Column(String(80), default="")
    created_at = Column(DateTime, default=utcnow, index=True)
    deleted_at = Column(DateTime, nullable=True)

    place = relationship("Place", lazy="joined")
    media = relationship("Media", uselist=False, back_populates="record", lazy="select")
    people = relationship("Person", secondary="record_people", lazy="selectin")

    @property
    def display_text(self) -> str:
        return (self.text or self.transcript or self.caption or "").strip()


class Media(Base):
    __tablename__ = "media"
    id = Column(Integer, primary_key=True)
    record_id = Column(Integer, ForeignKey("records.id"), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mime = Column(String(80), nullable=False)
    size = Column(Integer, default=0)
    data = Column(LargeBinary, nullable=False)  # small, client-compressed; swap for object storage later
    record = relationship("Record", back_populates="media")


class Person(Base):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String(120), nullable=False)
    relation = Column(String(80), default="")
    created_at = Column(DateTime, default=utcnow)


class RecordPerson(Base):
    __tablename__ = "record_people"
    record_id = Column(Integer, ForeignKey("records.id"), primary_key=True)
    person_id = Column(Integer, ForeignKey("people.id"), primary_key=True)


class CareLink(Base):
    __tablename__ = "care_links"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    caregiver_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    revoked_at = Column(DateTime, nullable=True)
    patient = relationship("User", foreign_keys=[patient_id], lazy="joined")
    caregiver = relationship("User", foreign_keys=[caregiver_id], lazy="joined")


class LinkCode(Base):
    __tablename__ = "link_codes"
    code = Column(String(8), primary_key=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)


class QueryLog(Base):
    __tablename__ = "query_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    question = Column(Text, nullable=False)
    provider = Column(String(80), default="")
    time_window = Column(JSON, nullable=True)
    retrieved = Column(JSON, default=list)  # [{id, score}]
    draft = Column(JSON, default=list)  # claims as the model wrote them
    accepted = Column(JSON, default=list)  # claims that passed the GroundingGuard
    dropped = Column(JSON, default=list)  # claims removed, with the reason
    answer = Column(Text, default="")
    refused = Column(Boolean, default=False)
    refusal_reason = Column(String(60), default="")
    latency_ms = Column(Integer, default=0)
    source = Column(String(20), default="app")  # app | eval
    created_at = Column(DateTime, default=utcnow, index=True)


class AccessLog(Base):
    __tablename__ = "access_logs"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(40), nullable=False)
    detail = Column(String(300), default="")
    created_at = Column(DateTime, default=utcnow, index=True)
    actor = relationship("User", foreign_keys=[actor_id], lazy="joined")


class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String(160), nullable=False)
    time_hhmm = Column(String(5), nullable=False)  # local time, e.g. "08:00"
    active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class ReminderEvent(Base):
    __tablename__ = "reminder_events"
    __table_args__ = (UniqueConstraint("reminder_id", "local_date"),)
    id = Column(Integer, primary_key=True)
    reminder_id = Column(Integer, ForeignKey("reminders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    local_date = Column(String(10), nullable=False)  # YYYY-MM-DD in the user's time zone
    done_at = Column(DateTime, default=utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    kind = Column(String(20), default="sos")
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

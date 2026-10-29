"""Builds the per-person Redactor used before anything is sent to an external model."""
from sqlalchemy.orm import Session

from ..domain.privacy import Redactor
from ..models import CareLink, Person, Place, User


def build_redactor(db: Session, patient: User) -> Redactor:
    people = {p.id: p.name for p in db.query(Person).filter(Person.user_id == patient.id)}
    places = {p.id: p.name for p in db.query(Place).filter(Place.user_id == patient.id)}
    family = {l.caregiver_id: l.caregiver.name for l in db.query(CareLink).filter(CareLink.patient_id == patient.id)}
    return Redactor(people=people, places=places, family=family, user_name=patient.name)

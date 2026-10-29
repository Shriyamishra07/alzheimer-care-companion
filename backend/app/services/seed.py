"""Corpus A: one synthetic persona we wrote ourselves.

Because we authored every memory, we know exactly what a correct answer looks
like, which is what makes an unsupported claim detectable (Review I, Dataset).
No real patient data is used anywhere.

Persona: Suresh Patil, 68, retired school teacher living alone in Thane.
Daughter Anita (caregiver), grandson Aarav, friend Ramesh, neighbour Mrs. Deshpande.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..domain import geohash as gh
from ..models import (AccessLog, Alert, CareLink, LinkCode, Media, Person, Place, QueryLog, Record, RecordPerson,
                      Reminder, ReminderEvent, User)
from ..security import hash_password

PLACES = {
    "home": ("Home, Vasant Vihar", 19.2305, 72.9612),
    "upvan": ("Upvan Lake", 19.2247, 72.9538),
    "temple": ("Kopineshwar Temple", 19.1953, 72.9749),
    "clinic": ("Dr. Kulkarni's Clinic", 19.2248, 72.9690),
    "mall": ("Viviana Mall", 19.2089, 72.9714),
    "kirana": ("Sai Kripa Kirana Store", 19.2321, 72.9645),
    "ramesh": ("Ramesh's House, Pokhran Road", 19.2199, 72.9667),
    "station": ("Thane Railway Station", 19.1863, 72.9756),
}

PEOPLE = {
    "anita": ("Anita", "Daughter"),
    "aarav": ("Aarav", "Grandson"),
    "ramesh": ("Ramesh Joshi", "Friend"),
    "deshpande": ("Mrs. Deshpande", "Neighbour"),
    "kulkarni": ("Dr. Kulkarni", "Family doctor"),
    "raju": ("Raju", "Kirana shop owner"),
}

# key, days_ago, "HH:MM" local, place, kind, text, people, private
RECORDS = [
    ("a01", 0, "07:30", "upvan", "text", "Morning walk around Upvan Lake with Ramesh. We fed the fish near the boating point.", ["ramesh"], False),
    ("a02", 0, "09:10", "home", "log", "Marked 'Morning tablet' as done.", [], False),
    ("a03", 0, "11:00", "home", "text", "Kept my reading glasses in the drawer of the TV table.", [], False),
    ("a04", 0, "13:30", "home", "text", "Anita called on video. Aarav won second prize in the school drawing competition.", ["anita", "aarav"], False),
    ("a05", 1, "10:00", "kirana", "text", "Bought milk, bread and two packets of Parle-G from Raju's shop. Paid 145 rupees.", ["raju"], False),
    ("a06", 1, "17:30", "temple", "text", "Evening aarti at Kopineshwar Temple with Mrs. Deshpande. Took prasad home for Anita.", ["deshpande"], False),
    ("a07", 1, "20:00", "home", "text", "Watched the India cricket match on TV. India won by 6 wickets.", [], False),
    ("a08", 2, "11:00", "clinic", "text", "Check-up with Dr. Kulkarni. Next appointment is on the 15th of next month. He said to keep walking every morning.", ["kulkarni"], False),
    ("a09", 3, "18:00", "ramesh", "text", "Played carrom at Ramesh's house. Ramesh won two games and I won one.", ["ramesh"], False),
    ("a10", 4, "12:00", "mall", "text", "Went to Viviana Mall with Anita and Aarav. Aarav got new school shoes from Bata. We ate dosa at the food court.", ["anita", "aarav"], False),
    ("a11", 5, "08:00", "home", "text", "Car keys are hanging on the hook behind the main door.", [], False),
    ("a12", 6, "07:15", "upvan", "text", "Walked around Upvan Lake alone. Met Mr. Rao, a retired bank manager who also walks there every day.", [], False),
    ("a13", 7, "19:00", "home", "text", "Anita's birthday is on 4 November. I want to buy a saree for her.", ["anita"], False),
    ("a14", 8, "10:30", "kirana", "text", "Raju said the shop will be closed on Tuesday for a family wedding.", ["raju"], False),
    ("a15", 9, "17:45", "temple", "text", "Donated 500 rupees at Kopineshwar Temple for the Navratri decoration.", [], False),
    ("a16", 10, "16:00", "home", "text", "Mrs. Deshpande brought modaks for Ganpati. They were very sweet.", ["deshpande"], False),
    ("a17", 12, "11:00", "clinic", "text", "Blood test at Dr. Kulkarni's clinic. The report will come on Friday.", ["kulkarni"], False),
    ("a18", 14, "18:30", "ramesh", "text", "Ramesh showed me photos of his trip to Nashik. His grandson is studying engineering in Pune.", ["ramesh"], False),
    ("a19", 15, "07:40", "upvan", "text", "Saw a big group of cormorants on Upvan Lake. Ramesh says they come every year after the rains.", ["ramesh"], False),
    ("a20", 18, "12:30", "mall", "text", "Paid the electricity bill at the counter in Viviana Mall. The bill was 1860 rupees.", [], False),
    ("a21", 20, "20:00", "home", "text", "Aarav stayed overnight. We read the Panchatantra story about the monkey and the crocodile.", ["aarav"], False),
    ("a22", 22, "09:00", "home", "text", "Plumber Sunil fixed the kitchen tap. His number is written on the fridge calendar.", [], False),
    ("a23", 25, "17:00", "temple", "text", "Met my old student Priya at the temple. She is now a teacher at Saraswati School.", [], False),
    ("a24", 28, "11:15", "kirana", "text", "Ordered a new gas cylinder through Raju. It will come on Thursday.", ["raju"], False),
    ("a25", 30, "18:00", "ramesh", "text", "Ramesh's wife made puran poli. We talked about our school days in Kolhapur.", ["ramesh"], False),
    ("a26", 35, "10:00", "clinic", "text", "Dr. Kulkarni checked my blood pressure. He said it was normal.", ["kulkarni"], False),
    ("a27", 40, "16:30", "mall", "text", "Bought a new watch battery at the Titan shop in Viviana Mall.", [], False),
    ("a28", 45, "07:00", "upvan", "text", "Yoga session near Upvan Lake. The yoga teacher's name is Meena.", [], False),
    ("a29", 16, "09:30", "station", "text", "Took the train from Thane station to Dadar to meet my sister Kusum.", [], False),
    ("p01", 3, "22:00", "home", "text", "Worried about the money for Aarav's school fees. Do not tell Anita yet.", ["aarav"], True),
    ("p02", 11, "21:00", "home", "text", "Missed Sunita a lot today. Looked at our wedding album.", [], True),
    ("p03", 19, "14:00", "home", "text", "The bank locker key is inside the steel cupboard, top shelf, under the towels.", [], True),
]

REMINDERS = [("Morning tablet", "09:00", "medication", "The blood pressure tablet, after breakfast."),
             ("Drink a glass of water", "12:00", "activity", ""),
             ("Evening walk", "17:30", "activity", "A short walk around the building.")]


def _at(now_utc: datetime, days_ago: int, hhmm: str, tz: int, idx: int) -> datetime:
    local_now = now_utc + timedelta(minutes=tz)
    h, m = map(int, hhmm.split(":"))
    local_dt = (local_now - timedelta(days=days_ago)).replace(hour=h, minute=m, second=0, microsecond=0)
    if local_dt > local_now:  # a "today" memory can't be in the future; keep order, pull it back
        local_dt = local_now - timedelta(minutes=30 + 10 * (10 - idx))
    return local_dt - timedelta(minutes=tz)


def purge_user(db: Session, user_id: int):
    rec_ids = [r.id for r in db.query(Record.id).filter(Record.user_id == user_id)]
    if rec_ids:
        db.query(RecordPerson).filter(RecordPerson.record_id.in_(rec_ids)).delete(synchronize_session=False)
        db.query(Media).filter(Media.record_id.in_(rec_ids)).delete(synchronize_session=False)
    rem_ids = [r.id for r in db.query(Reminder.id).filter(Reminder.user_id == user_id)]
    if rem_ids:
        db.query(ReminderEvent).filter(ReminderEvent.reminder_id.in_(rem_ids)).delete(synchronize_session=False)
    for model, col in ((Record, Record.user_id), (Person, Person.user_id), (Place, Place.user_id),
                       (QueryLog, QueryLog.user_id), (Reminder, Reminder.user_id), (Alert, Alert.patient_id),
                       (AccessLog, AccessLog.patient_id), (LinkCode, LinkCode.patient_id),
                       (CareLink, CareLink.patient_id)):
        db.query(model).filter(col == user_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    db.commit()
    db.expunge_all()  # forget cached rows so a re-used id doesn't clash


def seed_persona(db: Session, email: str, name: str = "Suresh Patil", is_system: bool = False,
                 password: str = "demo1234", tz: int = 330, now: datetime | None = None) -> tuple[User, dict]:
    now = now or datetime.utcnow()
    patient = User(name=name, email=email, password_hash=hash_password(password), role="patient",
                   phone="", is_system=is_system, created_at=now - timedelta(days=60))
    db.add(patient)
    db.flush()

    places = {}
    for key, (pname, lat, lng) in PLACES.items():
        p = Place(user_id=patient.id, name=pname, lat=lat, lng=lng, geohash=gh.encode(lat, lng, 7), record_count=0,
                  created_at=now - timedelta(days=60), last_visit_at=now - timedelta(days=60))
        db.add(p)
        places[key] = p
    people = {}
    for key, (pname, rel) in PEOPLE.items():
        person = Person(user_id=patient.id, name=pname, relation=rel)
        db.add(person)
        people[key] = person
    db.flush()

    keymap = {}
    for idx, (key, days, hhmm, pkey, kind, text, pkeys, private) in enumerate(RECORDS):
        when = _at(now, days, hhmm, tz, idx)
        place = places[pkey]
        rec = Record(user_id=patient.id, created_by=patient.id, kind=kind, text=text, lat=place.lat, lng=place.lng,
                     place_id=place.id, is_private=private, created_at=when)
        db.add(rec)
        db.flush()
        for pk in pkeys:
            db.add(RecordPerson(record_id=rec.id, person_id=people[pk].id))
        place.record_count += 1
        place.last_visit_at = max(place.last_visit_at, when)
        keymap[key] = rec.id

    for title, hhmm, kind, note in REMINDERS:
        rem = Reminder(user_id=patient.id, title=title, time_hhmm=hhmm, kind=kind, note=note, created_by=patient.id)
        db.add(rem)
        db.flush()
        if title == "Morning tablet":
            local_date = (now + timedelta(minutes=tz)).strftime("%Y-%m-%d")
            db.add(ReminderEvent(reminder_id=rem.id, user_id=patient.id, local_date=local_date,
                                 done_at=_at(now, 0, "09:10", tz, 1)))
    db.commit()
    return patient, keymap


def seed_demo(db: Session):
    """Demo accounts shown on the sign-in screen. Created once, on an empty database."""
    if db.query(User).filter(User.is_system.is_(False)).count() == 0:
        patient, _ = seed_persona(db, "suresh@demo.in")
        anita = User(name="Anita Patil", email="anita@demo.in", password_hash=hash_password("demo1234"),
                     role="caregiver", phone="+91 98200 00000")
        db.add(anita)
        db.flush()
        db.add(CareLink(patient_id=patient.id, caregiver_id=anita.id, role="primary", relation="Daughter",
                        created_at=datetime.utcnow() - timedelta(days=30)))
        db.add(AccessLog(patient_id=patient.id, actor_id=anita.id, action="view_dashboard", detail="Opened the dashboard",
                         created_at=datetime.utcnow() - timedelta(hours=20)))
        db.add(AccessLog(patient_id=patient.id, actor_id=anita.id, action="view_memories", detail="Looked at memories",
                         created_at=datetime.utcnow() - timedelta(hours=19)))
        db.commit()
    demo_extras(db)


def demo_extras(db: Session):
    """Features added after Review II, also added to demo databases that already exist. Safe to repeat."""
    patient = db.query(User).filter(User.email == "suresh@demo.in").first()
    anita = db.query(User).filter(User.email == "anita@demo.in").first()
    if not patient or not anita:
        return
    anita_link = (db.query(CareLink).filter(CareLink.patient_id == patient.id, CareLink.caregiver_id == anita.id,
                                            CareLink.revoked_at.is_(None)).first())
    if anita_link and not anita_link.relation:
        anita_link.relation = "Daughter"
    # A second caregiver with limited access, to show the primary caregiver's controls.
    rohan = db.query(User).filter(User.email == "rohan@demo.in").first()
    if not rohan:
        rohan = User(name="Rohan Patil", email="rohan@demo.in", password_hash=hash_password("demo1234"),
                     role="caregiver", phone="+91 98200 11111")
        db.add(rohan)
        db.flush()
        db.add(CareLink(patient_id=patient.id, caregiver_id=rohan.id, role="secondary", relation="Nephew",
                        invited_by=anita.id, created_at=datetime.utcnow() - timedelta(days=12),
                        permissions={"memories": False, "places": False, "reminders": True, "messages": True,
                                     "add_memories": False, "alerts": True}))
        db.add(AccessLog(patient_id=patient.id, actor_id=anita.id, action="invited", detail="Invited Rohan (nephew)",
                         created_at=datetime.utcnow() - timedelta(days=12, hours=1)))
    # Reminder types and notes for the original demo reminders.
    for title, _hhmm, kind, note in REMINDERS:
        r = db.query(Reminder).filter(Reminder.user_id == patient.id, Reminder.title == title).first()
        if r and (r.kind in (None, "", "other")):
            r.kind, r.note = kind, r.note or note
    # An upcoming appointment, a one-time reminder.
    today_local = (datetime.utcnow() + timedelta(minutes=330)).date()
    has_appt = db.query(Reminder).filter(Reminder.user_id == patient.id, Reminder.kind == "appointment",
                                         Reminder.active.is_(True)).all()
    if not any((r.on_date or "") >= today_local.isoformat() for r in has_appt):
        db.add(Reminder(user_id=patient.id, title="Check-up with Dr. Kulkarni", time_hhmm="11:00", kind="appointment",
                        note="Take the blood test report. Anita will come with you.", repeat_mode="once",
                        on_date=(today_local + timedelta(days=2)).isoformat(), created_by=anita.id))
    db.commit()

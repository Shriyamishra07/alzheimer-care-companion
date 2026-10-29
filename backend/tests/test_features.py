"""Tests for the features added after Review II:
  1. primary caregiver and per-caregiver permissions
  2. voice reminders
  3. personal details never reach the language model
Most are negative tests: they try to get past a rule and expect to be stopped."""
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.domain.privacy import Redactor, strip_jpeg_metadata
from app.main import app

PW = "secret123"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def login(c, email, pw="demo1234"):
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


def register(c, email, role, name="Test Person"):
    r = c.post("/api/auth/register", json={"name": name, "email": email, "password": PW, "role": role})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


def today_local(days=0):
    return (datetime.utcnow() + timedelta(minutes=330) + timedelta(days=days)).strftime("%Y-%m-%d")


# =========================================================== 3. privacy: domain
def _redactor():
    return Redactor(people={1: "Anita", 2: "Ramesh Joshi", 3: "Dr. Kulkarni"}, places={7: "Upvan Lake", 8: "Dr. Kulkarni's Clinic"},
                    family={40: "Anita Patil"}, user_name="Suresh Patil")


def test_redactor_hides_names_places_and_identifiers():
    r = _redactor()
    text = ("Suresh walked around Upvan Lake with Ramesh, then Anita's appointment at Dr. Kulkarni's Clinic. "
            "Call 98765 43210 or +91 98200 00000, mail suresh.patil@gmail.com. Aadhaar 2345 6789 0123, "
            "PAN ABCDE1234F, card 4111 1111 1111 1111, PIN 400706, at 19.2183, 72.9781.")
    out = r.redact(text)
    for secret in ("Suresh", "Upvan", "Ramesh", "Anita", "Kulkarni", "98765", "98200", "gmail", "2345 6789",
                   "ABCDE1234F", "4111", "400706", "19.2183"):
        assert secret not in out, (secret, out)
    for token in ("USER", "PLACE_7", "PERSON_2", "PERSON_1", "PLACE_8", "PHONE_", "EMAIL_", "AADHAAR_", "PAN_", "CARD_", "PINCODE_", "COORD_"):
        assert token in out, (token, out)
    # the model's reply comes back with tokens; the server restores the real words
    assert r.restore("You met PERSON_1 at PLACE_7.") == "You met Anita at Upvan Lake."


def test_redactor_tokens_are_stable_between_requests():
    a, b = _redactor(), _redactor()
    t = "Tea with Ramesh at Upvan Lake, call 98765 43210"
    assert a.redact(t) == b.redact(t)          # cached embeddings stay valid


def test_redactor_leaves_ordinary_text_alone():
    r = _redactor()
    t = "Kept my reading glasses in the drawer of the TV table at 11:00 AM on 25 September 2026."
    assert r.redact(t) == t


def test_strip_jpeg_metadata_removes_exif_gps():
    app1 = b"\xff\xe1" + (2 + 14).to_bytes(2, "big") + b"Exif\x00\x00GPS-DATA"
    app0 = b"\xff\xe0" + (2 + 5).to_bytes(2, "big") + b"JFIF\x00"
    jpeg = b"\xff\xd8" + app0 + app1 + b"\xff\xda\x00\x02" + b"pixels" + b"\xff\xd9"
    out = strip_jpeg_metadata(jpeg)
    assert b"Exif" not in out and b"GPS-DATA" not in out
    assert b"JFIF" in out and out.endswith(b"pixels\xff\xd9")
    assert strip_jpeg_metadata(b"not a jpeg") == b"not a jpeg"


# =========================================================== 1. care team and permissions
def test_demo_has_primary_and_limited_secondary(c):
    h, _ = login(c, "anita@demo.in")
    pid = c.get("/api/care/links", headers=h).json()[0]["person"]["id"]
    team = c.get(f"/api/care/team/{pid}", headers=h).json()
    assert team["can_manage"] is True
    roles = {m["name"]: m["role"] for m in team["members"]}
    assert roles["Anita Patil"] == "primary" and roles["Rohan Patil"] == "secondary"
    rohan = next(m for m in team["members"] if m["name"] == "Rohan Patil")
    assert rohan["permissions"]["memories"] is False and rohan["permissions"]["reminders"] is True

    hr, _ = login(c, "rohan@demo.in")
    t2 = c.get(f"/api/care/team/{pid}", headers=hr).json()
    assert t2["can_manage"] is False
    anita_seen_by_rohan = next(m for m in t2["members"] if m["name"] == "Anita Patil")
    assert anita_seen_by_rohan["permissions"] is None        # a secondary can't see others' permissions


def _pid(c):
    _, u = login(c, "suresh@demo.in")
    return u["id"]


def test_secondary_is_blocked_from_what_was_not_shared(c):
    pid = _pid(c)
    h, _ = login(c, "rohan@demo.in")
    assert c.get(f"/api/records?patient_id={pid}", headers=h).status_code == 403
    assert c.get(f"/api/places?patient_id={pid}", headers=h).status_code == 403
    assert c.get(f"/api/people?patient_id={pid}", headers=h).status_code == 403
    r = c.post("/api/records", headers=h, data={"kind": "text", "text": "Sneaky memory", "patient_id": str(pid)})
    assert r.status_code == 403
    # but what was shared works
    assert c.get(f"/api/reminders?patient_id={pid}", headers=h).status_code == 200
    assert c.get(f"/api/alerts?patient_id={pid}", headers=h).status_code == 200
    m = c.post("/api/records", headers=h, data={"kind": "message", "text": "See you Sunday", "patient_id": str(pid)})
    assert m.status_code == 200
    d = c.get(f"/api/care/dashboard/{pid}", headers=h).json()
    assert d["recent"] is None and d["week"] is None and d["today"] is None    # memories not shared
    assert d["reminders"] is not None and d["access"]["role"] == "secondary"


def test_secondary_cannot_manage_the_team(c):
    pid = _pid(c)
    h, _ = login(c, "rohan@demo.in")
    team = c.get(f"/api/care/team/{pid}", headers=h).json()
    anita_link = next(m["link_id"] for m in team["members"] if m["name"] == "Anita Patil")
    my_link = next(m["link_id"] for m in team["members"] if m["is_you"])
    assert c.post(f"/api/care/team/{pid}/invite", headers=h, json={"label": "x"}).status_code == 403
    assert c.patch(f"/api/care/links/{my_link}", headers=h, json={"permissions": {"memories": True}}).status_code == 403
    assert c.post(f"/api/care/links/{anita_link}/revoke", headers=h).status_code == 403
    assert c.post(f"/api/care/links/{my_link}/make-primary", headers=h).status_code == 403


def test_primary_changes_what_a_secondary_sees(c):
    pid = _pid(c)
    ha, _ = login(c, "anita@demo.in")
    hr, _ = login(c, "rohan@demo.in")
    team = c.get(f"/api/care/team/{pid}", headers=ha).json()
    rohan_link = next(m["link_id"] for m in team["members"] if m["name"] == "Rohan Patil")
    base = {"memories": False, "places": False, "reminders": True, "messages": True, "add_memories": False, "alerts": True}
    r = c.patch(f"/api/care/links/{rohan_link}", headers=ha, json={"permissions": {**base, "memories": True}})
    assert r.status_code == 200
    assert c.get(f"/api/records?patient_id={pid}", headers=hr).status_code == 200
    rows = c.get(f"/api/records?patient_id={pid}", headers=hr).json()
    assert not any(x["is_private"] for x in rows)                      # private memories still never shown
    c.patch(f"/api/care/links/{rohan_link}", headers=ha, json={"permissions": base})
    assert c.get(f"/api/records?patient_id={pid}", headers=hr).status_code == 403
    # the person sees the change in "Who saw my data"
    hp, _ = login(c, "suresh@demo.in")
    events = c.get("/api/privacy/log", headers=hp).json()["events"]
    assert any(e["action"] == "permissions_changed" for e in events)
    # nobody can reduce the primary caregiver's access
    anita_link = next(m["link_id"] for m in team["members"] if m["name"] == "Anita Patil")
    assert c.patch(f"/api/care/links/{anita_link}", headers=ha, json={"permissions": {"memories": False}}).status_code == 400


def test_primary_invites_with_chosen_permissions_then_removes(c):
    pid = _pid(c)
    ha, _ = login(c, "anita@demo.in")
    perms = {"memories": False, "places": False, "reminders": True, "messages": False, "add_memories": False, "alerts": True}
    inv = c.post(f"/api/care/team/{pid}/invite", headers=ha, json={"label": "Meera (home nurse)", "permissions": perms})
    assert inv.status_code == 200 and inv.json()["role"] == "secondary"
    hn, _ = register(c, "meera.nurse@test.in", "caregiver", "Meera Shah")
    link = c.post("/api/care/link", headers=hn, json={"code": inv.json()["code"]})
    assert link.status_code == 200 and link.json()["role"] == "secondary"
    assert link.json()["permissions"] == perms and link.json()["relation"] == "Meera (home nurse)"
    assert c.post("/api/records", headers=hn, data={"kind": "message", "text": "Hi", "patient_id": str(pid)}).status_code == 403
    d = c.get(f"/api/care/dashboard/{pid}", headers=hn).json()
    assert d["messages"] is None and d["reminders"] is not None
    # the code worked once only
    hx, _ = register(c, "someone.else@test.in", "caregiver")
    assert c.post("/api/care/link", headers=hx, json={"code": inv.json()["code"]}).status_code == 400
    # the primary removes her; she loses access at once
    assert c.post(f"/api/care/links/{link.json()['id']}/revoke", headers=ha).status_code == 200
    assert c.get(f"/api/care/dashboard/{pid}", headers=hn).status_code == 403


def test_cancelled_invite_cannot_be_used(c):
    pid = _pid(c)
    ha, _ = login(c, "anita@demo.in")
    code = c.post(f"/api/care/team/{pid}/invite", headers=ha, json={"label": "Cousin"}).json()["code"]
    assert c.post(f"/api/care/codes/{code}/cancel", headers=ha).status_code == 200
    hx, _ = register(c, "cousin@test.in", "caregiver")
    assert c.post("/api/care/link", headers=hx, json={"code": code}).status_code == 400


def test_transfer_primary_and_no_automatic_promotion(c):
    hp, patient = register(c, "own.patient@test.in", "patient", "Kamala Iyer")
    ha, _ = register(c, "first.carer@test.in", "caregiver", "First Carer")
    hb, _ = register(c, "second.carer@test.in", "caregiver", "Second Carer")
    la = c.post("/api/care/link", headers=ha, json={"code": c.post("/api/care/code", headers=hp).json()["code"]}).json()
    lb = c.post("/api/care/link", headers=hb, json={"code": c.post("/api/care/code", headers=hp).json()["code"]}).json()
    assert la["role"] == "primary" and lb["role"] == "secondary"
    # the person removes the primary: nobody is promoted automatically (no surprise full access)
    assert c.post(f"/api/care/links/{la['id']}/revoke", headers=hp).status_code == 200
    team = c.get(f"/api/care/team/{patient['id']}", headers=hp).json()
    assert [m["role"] for m in team["members"]] == ["secondary"]
    # the person chooses the new primary
    assert c.post(f"/api/care/links/{lb['id']}/make-primary", headers=hp).status_code == 200
    team = c.get(f"/api/care/team/{patient['id']}", headers=hp).json()
    assert team["members"][0]["role"] == "primary"
    # a caregiver can always leave
    assert c.post(f"/api/care/links/{lb['id']}/revoke", headers=hb).status_code == 200
    assert c.get(f"/api/care/dashboard/{patient['id']}", headers=hb).status_code == 403


def test_help_alert_location_only_with_places_permission(c):
    pid = _pid(c)
    hp, _ = login(c, "suresh@demo.in")
    c.post("/api/sos", headers=hp, json={"lat": 19.2183, "lng": 72.9781})
    hr, _ = login(c, "rohan@demo.in")
    a = c.get(f"/api/alerts?patient_id={pid}", headers=hr).json()[0]
    assert a["lat"] is None and a["location_hidden"] is True
    ha, _ = login(c, "anita@demo.in")
    a2 = c.get(f"/api/alerts?patient_id={pid}", headers=ha).json()[0]
    assert a2["lat"] == 19.2183
    c.post(f"/api/alerts/{a2['id']}/resolve", headers=ha)


# =========================================================== 2. voice reminders
def test_reminder_types_and_one_time_appointments(c):
    h, _ = login(c, "suresh@demo.in")
    body = {"title": "Eye check-up", "time": "10:30", "kind": "appointment", "repeat": "once", "on_date": today_local(3),
            "note": "Bring the old glasses", "speak": True}
    assert c.post("/api/reminders", headers=h, json=body).status_code == 200
    today = c.get("/api/reminders", headers=h).json()
    upcoming = c.get("/api/reminders?scope=all", headers=h).json()
    assert not any(r["title"] == "Eye check-up" for r in today)
    eye = next(r for r in upcoming if r["title"] == "Eye check-up")
    assert eye["status"] == "upcoming" and eye["kind"] == "appointment" and eye["note"] == "Bring the old glasses"
    assert c.post("/api/reminders", headers=h, json={**body, "on_date": today_local(-1)}).status_code == 400
    assert c.post("/api/reminders", headers=h, json={**body, "kind": "dose"}).status_code == 400
    assert c.post("/api/reminders", headers=h, json={**body, "on_date": None}).status_code == 400


def test_voice_message_on_a_reminder(c):
    pid = _pid(c)
    hr, _ = login(c, "rohan@demo.in")        # secondary WITH the reminders permission
    r = c.post("/api/reminders", headers=hr, json={"title": "Night tablet", "time": "21:00", "kind": "medication",
                                                   "patient_id": pid})
    assert r.status_code == 200
    rid = r.json()["id"]
    up = c.post(f"/api/reminders/{rid}/voice", headers=hr, files={"file": ("v.webm", b"\x1aE\xdf\xa3fake-audio", "audio/webm")})
    assert up.status_code == 200
    url = up.json()["voice_url"]
    got = c.get(url)
    assert got.status_code == 200 and got.headers["content-type"].startswith("audio/webm")
    assert c.get(url.replace("sig=", "sig=0")).status_code == 403
    bad = c.post(f"/api/reminders/{rid}/voice", headers=hr, files={"file": ("x.txt", b"hello", "text/plain")})
    assert bad.status_code == 400
    hp, _ = login(c, "suresh@demo.in")
    night = next(x for x in c.get("/api/reminders", headers=hp).json() if x["title"] == "Night tablet")
    assert night["voice_url"] and night["kind"] == "medication"


def test_caregiver_without_reminder_permission_cannot_touch_reminders(c):
    pid = _pid(c)
    ha, _ = login(c, "anita@demo.in")
    perms = {"memories": True, "places": False, "reminders": False, "messages": True, "add_memories": False, "alerts": True}
    code = c.post(f"/api/care/team/{pid}/invite", headers=ha, json={"label": "Friend", "permissions": perms}).json()["code"]
    hf, _ = register(c, "friend.noreminders@test.in", "caregiver")
    c.post("/api/care/link", headers=hf, json={"code": code})
    assert c.get(f"/api/reminders?patient_id={pid}", headers=hf).status_code == 403
    assert c.post("/api/reminders", headers=hf, json={"title": "x", "time": "10:00", "patient_id": pid}).status_code == 403
    rid = c.get(f"/api/reminders?patient_id={pid}", headers=ha).json()[0]["id"]
    assert c.delete(f"/api/reminders/{rid}", headers=hf).status_code == 403


# =========================================================== 3. privacy: API and the model boundary
def test_privacy_preview_shows_what_the_ai_would_see(c):
    h, _ = login(c, "suresh@demo.in")
    r = c.post("/api/privacy/preview", headers=h, json={"text": "Call Anita on 98765 43210 after the walk at Upvan Lake"})
    sent = r.json()["sent_to_ai"]
    assert "Anita" not in sent and "98765" not in sent and "Upvan" not in sent
    assert "PERSON_" in sent and "PHONE_" in sent and "PLACE_" in sent
    assert {x["type"] for x in r.json()["hidden"]} >= {"person", "phone", "place"}


def test_ai_media_consent_is_off_by_default_and_owner_only(c):
    h, u = login(c, "suresh@demo.in")
    assert u["ai_media_consent"] is False
    assert c.patch("/api/me", headers=h, json={"ai_media_consent": True}).json()["ai_media_consent"] is True
    assert c.patch("/api/me", headers=h, json={"ai_media_consent": False}).json()["ai_media_consent"] is False
    ha, _ = login(c, "anita@demo.in")
    assert c.patch("/api/me", headers=ha, json={"ai_media_consent": True}).status_code == 403


def test_uploaded_photo_has_no_location_metadata(c):
    h, _ = login(c, "suresh@demo.in")
    app1 = b"\xff\xe1" + (2 + 14).to_bytes(2, "big") + b"Exif\x00\x00GPS-DATA"
    jpeg = b"\xff\xd8" + app1 + b"\xff\xda\x00\x02" + b"pixels" + b"\xff\xd9"
    r = c.post("/api/records", headers=h, data={"kind": "photo", "text": "Balcony plants"},
               files={"file": ("p.jpg", jpeg, "image/jpeg")})
    stored = c.get(r.json()["media_url"]).content
    assert b"GPS-DATA" not in stored and b"pixels" in stored


class FakeGemini:
    """Stands in for the Gemini API and records every request body it receives."""

    def __init__(self):
        from app.providers.llm import GeminiProvider
        self.sent = []
        prov = GeminiProvider("test-key")
        fake = self

        def _post(path, body):
            fake.sent.append(json.dumps(body, ensure_ascii=False))
            if path.endswith(":batchEmbedContents"):
                return {"embeddings": [{"values": [1.0] + [0.0] * 767} for _ in body["requests"]]}
            system = body["systemInstruction"]["parts"][0]["text"]
            text = body["contents"][0]["parts"][0]["text"]
            if system.startswith("You help"):
                memories = json.loads(text.split("MEMORIES:\n", 1)[1])
                m = memories[0]
                reply = {"answer_found": True, "claims": [{"sentence": m["memory"], "record_ids": [m["id"]]}]}
            else:
                reply = {"verdicts": [True] * len(json.loads(text))}
            return {"candidates": [{"content": {"parts": [{"text": json.dumps(reply)}]}}]}

        prov._post = _post
        self.provider = prov


def test_nothing_personal_reaches_the_language_model(c):
    from app.db import SessionLocal
    from app.models import QueryLog, User
    from app.services.ask import answer_question
    h, _ = register(c, "privacy.persona@test.in", "patient", "Kamal Deshmukh")
    c.post("/api/people", headers=h, json={"name": "Lata", "relation": "Wife"})
    c.post("/api/records", headers=h, data={"kind": "text", "lat": "19.0760", "lng": "72.8777",
                                            "text": "Lata kept the spare house key in the blue tin. Her number is 98765 43210.",
                                            "new_people": "Lata"})
    fake = FakeGemini()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "privacy.persona@test.in").first()
        res = answer_question(db, user, "Where did Lata keep the spare key?", provider=fake.provider)
        log = db.get(QueryLog, res["query_id"])
        assert log.ai_payload, "the redacted request should be kept for the audit log"
    finally:
        db.close()
    assert fake.sent, "the fake model should have been called"
    everything_sent = " ".join(fake.sent)
    for secret in ("Lata", "Kamal", "Deshmukh", "98765", "43210"):
        assert secret not in everything_sent, f"{secret} reached the model"
    assert "PERSON_" in everything_sent and "PHONE_" in everything_sent
    assert not res["refused"] and "Lata" in res["answer"]           # restored on the server
    assert "Lata" not in json.dumps(res["ai_payload"])


# =========================================================== upgrade of an existing database
OLD_SCHEMA = [   # the tables exactly as they were deployed for Review II
    "CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, email VARCHAR(200) NOT NULL UNIQUE, "
    "password_hash VARCHAR(300) NOT NULL, role VARCHAR(20) NOT NULL, phone VARCHAR(30), is_system BOOLEAN, created_at DATETIME)",
    "CREATE TABLE care_links (id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL, caregiver_id INTEGER NOT NULL, "
    "created_at DATETIME, revoked_at DATETIME)",
    "CREATE TABLE link_codes (code VARCHAR(8) PRIMARY KEY, patient_id INTEGER NOT NULL, expires_at DATETIME NOT NULL, "
    "used_at DATETIME)",
    "CREATE TABLE reminders (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title VARCHAR(160) NOT NULL, "
    "time_hhmm VARCHAR(5) NOT NULL, active BOOLEAN, created_by INTEGER, created_at DATETIME)",
    "CREATE TABLE query_logs (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, question TEXT NOT NULL, provider VARCHAR(80), "
    "time_window JSON, retrieved JSON, draft JSON, accepted JSON, dropped JSON, answer TEXT, refused BOOLEAN, "
    "refusal_reason VARCHAR(60), latency_ms INTEGER, source VARCHAR(20), created_at DATETIME)",
]


def test_migration_upgrades_an_old_database(tmp_path):
    from sqlalchemy import create_engine, inspect, text
    from app.migrate import migrate
    eng = create_engine(f"sqlite:///{tmp_path}/old.db")
    with eng.begin() as con:
        for ddl in OLD_SCHEMA:
            con.execute(text(ddl))
        con.execute(text("INSERT INTO users (id, name, email, password_hash, role, is_system) VALUES "
                         "(1,'P','p@x','h','patient',0),(2,'A','a@x','h','caregiver',0),(3,'B','b@x','h','caregiver',0)"))
        con.execute(text("INSERT INTO care_links (patient_id, caregiver_id, created_at) VALUES "
                         "(1,2,'2026-01-01 10:00:00'),(1,3,'2026-02-01 10:00:00')"))
        con.execute(text("INSERT INTO reminders (user_id, title, time_hhmm, active) VALUES (1,'Tablet','09:00',1)"))
    added = migrate(eng)
    assert {"care_links.role", "care_links.permissions", "reminders.kind", "reminders.voice_data", "reminders.speak",
            "query_logs.ai_payload", "users.ai_media_consent", "link_codes.link_role"} <= set(added)
    cols = {c["name"] for c in inspect(eng).get_columns("care_links")}
    assert {"role", "permissions", "relation", "invited_by"} <= cols
    with eng.connect() as con:
        roles = con.execute(text("SELECT caregiver_id, role FROM care_links ORDER BY caregiver_id")).fetchall()
        rem = con.execute(text("SELECT kind, repeat_mode, speak FROM reminders")).fetchone()
    assert [tuple(r) for r in roles] == [(2, "primary"), (3, "secondary")]    # earliest caregiver became primary
    assert tuple(rem) == ("other", "daily", 1)                                  # old reminders keep working
    assert migrate(eng) == []                                                   # running again changes nothing

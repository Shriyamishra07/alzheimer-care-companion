"""API tests. Most of these are NEGATIVE tests: writing access rules is not
evidence that they work; a passing test that tries to break them is."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def login(c, email, pw="demo1234"):
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


def register(c, email, role, name="Test"):
    r = c.post("/api/auth/register", json={"name": name, "email": email, "password": "secret123", "role": role})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


def patient_id(c):
    _, u = login(c, "suresh@demo.in")
    return u["id"]


# ---------------- happy paths
def test_demo_patient_sees_own_memories(c):
    h, _ = login(c, "suresh@demo.in")
    rows = c.get("/api/records", headers=h).json()
    assert len(rows) >= 30 and any(r["is_private"] for r in rows)


def test_capture_creates_place_and_person(c):
    h, _ = login(c, "suresh@demo.in")
    r = c.post("/api/records", headers=h, data={"kind": "text", "text": "Tea with Kavita at the college canteen",
                                                 "lat": "19.0330", "lng": "73.0297", "new_people": "Kavita"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["place"] and body["people"][0]["name"] == "Kavita"
    # a second memory 40 m away joins the same place
    r2 = c.post("/api/records", headers=h, data={"kind": "text", "text": "Samosa at the canteen",
                                                  "lat": "19.0333", "lng": "73.0298"})
    assert r2.json()["place"]["id"] == body["place"]["id"]


def test_photo_upload_and_signed_url(c):
    h, _ = login(c, "suresh@demo.in")
    png = bytes.fromhex("89504E470D0A1A0A0000000D4948445200000001000000010806000000")
    r = c.post("/api/records", headers=h, data={"kind": "photo", "text": "Garden"},
               files={"file": ("a.png", png, "image/png")})
    url = r.json()["media_url"]
    assert c.get(url).status_code == 200
    assert c.get(url.replace("sig=", "sig=0")).status_code == 403  # tampered signature


def test_ask_answers_with_sources(c):
    h, _ = login(c, "suresh@demo.in")
    r = c.post("/api/ask", headers=h, json={"question": "Where did I keep my reading glasses?"}).json()
    assert not r["refused"] and r["sources"] and "TV table" in r["answer"]


def test_ask_refuses_when_nothing_matches(c):
    h, _ = login(c, "suresh@demo.in")
    r = c.post("/api/ask", headers=h, json={"question": "What did I eat in Goa?"}).json()
    assert r["refused"] and r["sources"] == []


def test_ask_refuses_medical_advice(c):
    h, _ = login(c, "suresh@demo.in")
    r = c.post("/api/ask", headers=h, json={"question": "Can I take two tablets tonight?"}).json()
    assert r["refused"] and r["reason"] == "medical_advice_request"


def test_ask_never_uses_private_memories(c):
    h, _ = login(c, "suresh@demo.in")
    r = c.post("/api/ask", headers=h, json={"question": "Where is the bank locker key?"}).json()
    assert "cupboard" not in r["answer"].lower()


def test_reminder_done_becomes_answerable(c):
    h, _ = login(c, "suresh@demo.in")
    rems = c.get("/api/reminders", headers=h).json()
    water = next(x for x in rems if "water" in x["title"].lower())
    c.post(f"/api/reminders/{water['id']}/done", headers=h)
    r = c.post("/api/ask", headers=h, json={"question": "Did I drink a glass of water today?"}).json()
    assert not r["refused"]


def test_caregiver_message_shows_for_patient_and_in_dashboard(c):
    h, _ = login(c, "anita@demo.in")
    pid = patient_id(c)
    r = c.post("/api/records", headers=h, data={"kind": "message", "text": "I am coming on Sunday!", "patient_id": str(pid)})
    assert r.status_code == 200 and r.json()["display_text"].startswith("Message from Anita:")
    hp, _ = login(c, "suresh@demo.in")
    msgs = c.get("/api/records?kind=message", headers=hp).json()
    assert msgs and "Sunday" in msgs[0]["display_text"]
    dash = c.get(f"/api/care/dashboard/{pid}", headers=h).json()
    assert len(dash["week"]) == 7 and dash["messages"]


def test_patient_cannot_write_a_family_message(c):
    hp, _ = login(c, "suresh@demo.in")
    assert c.post("/api/records", headers=hp, data={"kind": "message", "text": "hi"}).status_code == 400


# ---------------- negative tests: access that must be refused
def test_no_token_is_rejected(c):
    assert c.get("/api/records").status_code == 401


def test_bad_token_is_rejected(c):
    assert c.get("/api/records", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_unlinked_caregiver_cannot_read(c):
    h, _ = register(c, "stranger@test.in", "caregiver")
    assert c.get(f"/api/records?patient_id={patient_id(c)}", headers=h).status_code == 403
    assert c.get(f"/api/care/dashboard/{patient_id(c)}", headers=h).status_code == 403


def test_other_patient_cannot_read(c):
    h, _ = register(c, "other.patient@test.in", "patient")
    assert c.get(f"/api/records?patient_id={patient_id(c)}", headers=h).status_code == 403


def test_linked_caregiver_never_sees_private(c):
    h, _ = login(c, "anita@demo.in")
    rows = c.get(f"/api/records?patient_id={patient_id(c)}", headers=h).json()
    assert rows and not any(r["is_private"] for r in rows)
    texts = " ".join(r["display_text"] for r in rows).lower()
    assert "locker" not in texts and "school fees" not in texts


def test_caregiver_cannot_use_ask(c):
    h, _ = login(c, "anita@demo.in")
    assert c.post("/api/ask", headers=h, json={"question": "Where are the keys?"}).status_code == 403


def test_caregiver_cannot_delete_memories(c):
    hp, _ = login(c, "suresh@demo.in")
    rid = c.get("/api/records", headers=hp).json()[0]["id"]
    h, _ = login(c, "anita@demo.in")
    assert c.delete(f"/api/records/{rid}", headers=h).status_code == 403


def test_revoked_caregiver_loses_access_and_trace_remains(c):
    hp, _ = login(c, "suresh@demo.in")
    code = c.post("/api/care/code", headers=hp).json()["code"]
    hc, _ = register(c, "brother@test.in", "caregiver", name="Brother")
    assert c.post("/api/care/link", headers=hc, json={"code": code}).status_code == 200
    assert c.post("/api/care/link", headers=hc, json={"code": code}).status_code == 400  # code is single-use
    pid = patient_id(c)
    assert c.get(f"/api/records?patient_id={pid}", headers=hc).status_code == 200
    link = next(l for l in c.get("/api/care/links", headers=hp).json() if l["person"]["name"] == "Brother")
    c.post(f"/api/care/links/{link['id']}/revoke", headers=hp)
    assert c.get(f"/api/records?patient_id={pid}", headers=hc).status_code == 403
    after = next(l for l in c.get("/api/care/links", headers=hp).json() if l["id"] == link["id"])
    assert after["revoked_at"] is not None  # revoked, not deleted
    log = c.get("/api/privacy/log", headers=hp).json()["events"]
    assert any(e["who"] == "Brother" for e in log)


def test_cannot_edit_someone_elses_place(c):
    h, _ = register(c, "p3@test.in", "patient")
    hp, _ = login(c, "suresh@demo.in")
    pid = c.get("/api/places", headers=hp).json()[0]["id"]
    assert c.patch(f"/api/places/{pid}", headers=h, json={"name": "Mine now"}).status_code == 404


def test_system_persona_cannot_sign_in(c):
    hp, _ = login(c, "suresh@demo.in")
    c.post("/api/eval/run", headers=hp)
    r = c.post("/api/auth/login", json={"email": "eval.persona@system.local", "password": "demo1234"})
    assert r.status_code == 401


def test_evaluation_meets_targets_offline(c):
    hp, _ = login(c, "suresh@demo.in")
    rep = c.post("/api/eval/run", headers=hp).json()
    by_id = {m["id"]: m for m in rep["metrics"]}
    for k in ("NFR-AI-1", "NFR-AI-4", "NFR-AI-5", "NFR-AI-6"):
        assert by_id[k]["passed"], by_id[k]

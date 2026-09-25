"""Domain-layer tests: run on a laptop with no emulator, no network, no model."""
from datetime import datetime

from app.domain import geohash as gh
from app.domain.grounding import Claim, GroundingGuard, SourceRecord
from app.domain.retrieval import parse_time_window
from app.domain.safety import is_medical_advice_request, output_has_medical_advice
from app.domain.text import focus_coverage_ok, focus_terms, proper_nouns, tokenize

SRC = [
    SourceRecord(1, "Wednesday 23 September 2026, 7:30 AM at Upvan Lake. With Ramesh Joshi. Morning walk with Ramesh."),
    SourceRecord(2, "Tuesday 22 September 2026 at Home. Kept my reading glasses in the TV table drawer."),
    SourceRecord(3, "Sunday at Home. The bank locker key is in the steel cupboard.", is_private=True),
]


# ---------------- GroundingGuard
def test_guard_accepts_supported_claim():
    res = GroundingGuard().check([Claim("You walked with Ramesh at Upvan Lake this morning.", [1])], SRC)
    assert not res.refused and len(res.accepted) == 1


def test_guard_drops_claim_without_citation():
    res = GroundingGuard().check([Claim("You walked with Ramesh.", [])], SRC)
    assert res.refused and res.dropped[0]["reason"] == "no_citation"


def test_guard_drops_claim_citing_record_that_was_not_retrieved():
    res = GroundingGuard().check([Claim("You walked with Ramesh.", [99])], SRC)
    assert res.dropped[0]["reason"] == "cites_unretrieved_record"


def test_guard_drops_private_record():
    res = GroundingGuard().check([Claim("The locker key is in the steel cupboard.", [3])], SRC)
    assert res.dropped[0]["reason"] == "cites_private_record"


def test_guard_drops_invented_detail():
    # Cites a real record but adds facts that are not in it.
    res = GroundingGuard().check([Claim("You and Priya ate vada pav at Dadar station.", [1])], SRC)
    assert res.refused and res.dropped[0]["reason"] == "unsupported_words"


def test_guard_drops_medical_advice_even_if_cited():
    res = GroundingGuard().check([Claim("You should take 2 tablets with Ramesh.", [1])], SRC)
    assert res.dropped[0]["reason"] == "medical_advice"


def test_guard_uses_injected_verifier():
    res = GroundingGuard(verifier=lambda pairs: [False] * len(pairs)).check(
        [Claim("You walked with Ramesh at Upvan Lake.", [1])], SRC)
    assert res.refused and res.dropped[0]["reason"] == "verifier_rejected"


def test_guard_keeps_good_and_drops_bad_in_one_answer():
    res = GroundingGuard().check([Claim("You kept your reading glasses in the TV table drawer.", [2]),
                                  Claim("You bought a new phone.", [2])], SRC)
    assert len(res.accepted) == 1 and len(res.dropped) == 1


# ---------------- safety
def test_medical_advice_is_detected():
    for q in ["How many tablets should I take?", "Can I take paracetamol now?", "What dose is safe?",
              "Is it okay to skip my tablet today?"]:
        assert is_medical_advice_request(q), q


def test_log_lookup_is_not_advice():
    assert not is_medical_advice_request("Did I take my morning tablet today?")
    assert not is_medical_advice_request("When is my blood test report coming?")


def test_output_advice_filter():
    assert output_has_medical_advice("You should take two tablets.")
    assert not output_has_medical_advice("You marked the morning tablet as done.")


# ---------------- text / retrieval
def test_tokenize_lemmas_and_stems():
    assert tokenize("Kept glasses; shop closed") == ["keep", "glass", "shop", "clos"]


def test_focus_terms_ignore_generic_words():
    assert focus_terms("Where did I keep my reading glasses?") == {"read", "glass"}


def test_focus_coverage_rules():
    assert focus_coverage_ok({"car", "key"}, {"car", "key", "hook"})
    assert not focus_coverage_ok({"kusum", "cook"}, {"kusum", "train"})
    assert focus_coverage_ok({"bird", "upvan", "lak"}, {"upvan", "lak"})


def test_proper_nouns():
    assert proper_nouns("What did I eat in Goa?") == {"goa"}
    assert proper_nouns("where are my keys") == set()


def test_time_window_yesterday_in_ist():
    now = datetime(2026, 9, 23, 6, 0)  # 11:30 AM IST
    start, end = parse_time_window("What did I do yesterday?", now, 330)
    assert start == datetime(2026, 9, 21, 18, 30) and end == datetime(2026, 9, 22, 18, 30)


def test_no_time_window():
    assert parse_time_window("Where are my keys?", datetime(2026, 9, 23), 330) is None


# ---------------- geohash
def test_geohash_known_value():
    assert gh.encode(57.64911, 10.40744, 11) == "u4pruydqqvj"


def test_neighbours_cover_point_and_distance():
    cells = gh.neighbour_prefixes(19.2247, 72.9538, 6)
    assert len(cells) == 9 and gh.encode(19.2247, 72.9538, 6) in cells
    assert 900 < gh.haversine_m(19.2247, 72.9538, 19.2305, 72.9612) < 1100

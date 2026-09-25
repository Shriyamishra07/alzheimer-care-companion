"""Ask My Memories: the research contribution.

    question
      -> medical-advice check          (NFR-AI-5, before anything else)
      -> time window ("yesterday")     (narrows the search)
      -> unknown-name check            ("Goa" is not in this person's world -> refuse)
      -> retrieval, private excluded   (NFR-AI-6)
      -> nothing relevant? refuse      (NFR-AI-3, the model is never called)
      -> model writes cited claims
      -> GroundingGuard drops any claim it cannot trace (NFR-AI-1, NFR-AI-2)
      -> answer + sources              (NFR-AI-4)
      -> everything written to QueryLog, which the evaluation reads
"""
import time
from datetime import datetime

from sqlalchemy.orm import Session

from ..domain.grounding import REFUSAL_TEXT, GroundingGuard, SourceRecord
from ..domain.retrieval import Candidate, parse_time_window, rank
from ..domain.safety import MEDICAL_REPLY, is_medical_advice_request
from ..domain.text import content_tokens, focus_coverage_ok, focus_terms, proper_nouns, tokenize
from ..models import Person, Place, QueryLog, Record, User
from ..providers.llm import ProviderError, get_offline, get_provider
from .present import ai_item, iso, record_out


def _vectors(db: Session, provider, records: list[Record], items: dict) -> dict:
    """Offline vectors are cheap, computed each time. Model vectors are cached on the row."""
    if provider.name == "offline":
        return {r.id: v for r, v in zip(records, provider.embed_docs([items[r.id]["context"] for r in records]))}
    stale = [r for r in records if r.embed_model != provider.embed_name or not r.embedding]
    if stale:
        vecs = provider.embed_docs([items[r.id]["context"] for r in stale])
        for r, v in zip(stale, vecs):
            r.embedding, r.embed_model = v, provider.embed_name
        db.commit()
    return {r.id: r.embedding for r in records}


def _run(db: Session, user: User, question: str, tz: int, provider) -> dict:
    out = {"provider": provider.name, "window": None, "retrieved": [], "draft": [], "accepted": [], "dropped": []}
    now = datetime.utcnow()
    window = parse_time_window(question, now, tz)
    q = db.query(Record).filter(Record.user_id == user.id, Record.deleted_at.is_(None), Record.is_private.is_(False))
    if window:
        out["window"] = [iso(window[0]), iso(window[1])]
        q = q.filter(Record.created_at >= window[0], Record.created_at < window[1])
    records = q.all()
    if not records:
        return {**out, "refused": True, "reason": "no_memories_in_that_time" if window else "no_memories_yet"}

    items = {r.id: ai_item(r, tz) for r in records}
    places = db.query(Place).filter(Place.user_id == user.id).all()
    people = db.query(Person).filter(Person.user_id == user.id).all()

    # Names the person has never saved anywhere ("Goa", "Kusum's cooking") mean: say we don't know.
    known = set()
    for name in [p.name for p in places] + [p.name for p in people]:
        known.update(tokenize(name))
    for it in items.values():
        known.update(tokenize(it["context"]))
    unknown = proper_nouns(question) - known
    if unknown:
        return {**out, "refused": True, "reason": "unknown_name"}

    focus = focus_terms(question)

    # "What did I do today?" has a time but no topic: answer with that time's memories, in order.
    if window and not focus:
        ordered = sorted(records, key=lambda r: r.created_at)[-6:]
        top_items = [items[r.id] for r in ordered]
        out["retrieved"] = [{"id": it["id"], "score": 1.0} for it in top_items]
        claims = provider.generate_claims(question, top_items, max_items=6)
        return _guarded(out, provider, claims, top_items)

    place_hits = {p.id for p in places if set(content_tokens(p.name)) & focus}
    person_hits = {p.id for p in people if set(content_tokens(p.name)) & focus}

    qvec = provider.embed_query(question)
    vecs = _vectors(db, provider, records, items)
    cands = []
    for r in records:
        toks = set(content_tokens(items[r.id]["context"]))
        if provider.lexical_focus and not focus_coverage_ok(focus, toks):
            continue
        score = provider.similarity(qvec, vecs[r.id])
        if r.place_id in place_hits:
            score += 0.05
        if person_hits & {p.id for p in r.people}:
            score += 0.05
        cands.append(Candidate(r.id, round(score, 4), items[r.id]["context"], toks))

    top = rank(cands, provider.min_score, provider.relative, k=6)
    out["retrieved"] = [{"id": c.record_id, "score": c.score} for c in top]
    if not top:
        return {**out, "refused": True, "reason": "no_relevant_memory"}

    top_items = [items[c.record_id] for c in top]
    claims = provider.generate_claims(question, top_items)
    return _guarded(out, provider, claims, top_items)


def _guarded(out: dict, provider, claims, top_items) -> dict:
    out["draft"] = [{"sentence": c.sentence, "record_ids": c.record_ids} for c in claims]
    guard = GroundingGuard(verifier=provider.verifier)
    result = guard.check(claims, [SourceRecord(it["id"], it["context"], False) for it in top_items])
    out["accepted"] = [{"sentence": c.sentence, "record_ids": c.record_ids} for c in result.accepted]
    out["dropped"] = result.dropped
    if result.refused:
        return {**out, "refused": True, "reason": "guard_removed_everything" if claims else "model_found_nothing"}
    return {**out, "refused": False, "reason": ""}


def answer_question(db: Session, user: User, question: str, tz: int = 330, source: str = "app", provider=None) -> dict:
    t0 = time.perf_counter()
    provider = provider or get_provider()
    question = (question or "").strip()[:500]

    if is_medical_advice_request(question):
        res = {"provider": "rules", "window": None, "retrieved": [], "draft": [], "accepted": [], "dropped": [],
               "refused": True, "reason": "medical_advice_request"}
    else:
        try:
            res = _run(db, user, question, tz, provider)
        except ProviderError as e:
            res = _run(db, user, question, tz, get_offline())
            res["provider"] = f"offline (fallback: {str(e)[:60]})"

    if res["refused"]:
        answer = MEDICAL_REPLY if res["reason"] == "medical_advice_request" else REFUSAL_TEXT
    else:
        answer = " ".join(c["sentence"] for c in res["accepted"])

    cited = []
    for c in res["accepted"]:
        for i in c["record_ids"]:
            if i not in cited:
                cited.append(i)
    rec_map = {r.id: r for r in db.query(Record).filter(Record.id.in_(cited)).all()} if cited else {}

    log = QueryLog(user_id=user.id, question=question, provider=res["provider"], time_window=res["window"],
                   retrieved=res["retrieved"], draft=res["draft"], accepted=res["accepted"], dropped=res["dropped"],
                   answer=answer, refused=res["refused"], refusal_reason=res["reason"],
                   latency_ms=int((time.perf_counter() - t0) * 1000), source=source)
    db.add(log)
    db.commit()

    return {
        "query_id": log.id,
        "question": question,
        "answer": answer,
        "refused": res["refused"],
        "reason": res["reason"],
        "claims": [{"sentence": c["sentence"], "record_ids": c["record_ids"],
                    "source_numbers": [cited.index(i) + 1 for i in c["record_ids"]]} for c in res["accepted"]],
        "sources": [record_out(rec_map[i]) for i in cited if i in rec_map],
        "dropped": res["dropped"],
        "retrieved": res["retrieved"],
        "provider": res["provider"],
        "latency_ms": log.latency_ms,
    }

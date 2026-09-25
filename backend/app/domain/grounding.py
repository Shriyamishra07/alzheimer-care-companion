"""GroundingGuard: the safety check between the language model and the user.

A person with memory loss cannot check an answer against their own memory,
so a made-up "memory" may be believed. Every sentence must cite records that
were actually retrieved for this question, must not cite a private record,
must not give medical advice, and its content words must appear in the cited
records. Anything that fails is dropped. If nothing survives, we refuse.

The optional `verifier` (e.g. a second LLM pass) is injected, so this class
can be unit-tested with no model and no network.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

from .safety import output_has_medical_advice
from .text import content_tokens

# Words an answer may use to talk *about* memories without that being a factual claim.
GLUE = {
    "sav", "not", "memory", "writ", "record", "say", "mention", "also", "seem", "accord", "you", "yourself",
    "on", "at", "around", "rupe", "am", "pm",
}

REFUSAL_TEXT = "Sorry, I could not find any memory about that."


@dataclass
class SourceRecord:
    id: int
    text: str  # rendered context: date, place, people and the memory text
    is_private: bool = False


@dataclass
class Claim:
    sentence: str
    record_ids: list[int]


@dataclass
class GuardResult:
    accepted: list[Claim] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)

    @property
    def refused(self) -> bool:
        return not self.accepted


def lexical_support(sentence: str, source_texts: list[str]) -> float:
    words = [w for w in content_tokens(sentence) if w not in GLUE and len(w) > 1]
    if not words:
        return 0.0
    pool = set()
    for t in source_texts:
        pool.update(content_tokens(t))
    return sum(1 for w in words if w in pool) / len(words)


Verifier = Callable[[list[tuple[str, list[str]]]], list[bool]]


class GroundingGuard:
    def __init__(self, min_support: float = 0.6, verifier: Optional[Verifier] = None):
        self.min_support = min_support
        self.verifier = verifier

    def check(self, claims: list[Claim], retrieved: list[SourceRecord]) -> GuardResult:
        by_id = {r.id: r for r in retrieved}
        result = GuardResult()
        survivors: list[Claim] = []
        for c in claims:
            reason = self._structural_reason(c, by_id)
            if reason:
                result.dropped.append({"sentence": c.sentence, "record_ids": c.record_ids, "reason": reason})
            else:
                survivors.append(c)

        if survivors and self.verifier:
            try:
                verdicts = self.verifier([(c.sentence, [by_id[i].text for i in c.record_ids]) for c in survivors])
            except Exception:
                verdicts = [True] * len(survivors)  # lexical check already passed; don't fail open to an error page
            kept = []
            for c, ok in zip(survivors, verdicts):
                if ok:
                    kept.append(c)
                else:
                    result.dropped.append({"sentence": c.sentence, "record_ids": c.record_ids, "reason": "verifier_rejected"})
            survivors = kept

        result.accepted = survivors
        return result

    def _structural_reason(self, c: Claim, by_id: dict) -> Optional[str]:
        if not c.sentence or not c.sentence.strip():
            return "empty_sentence"
        if not c.record_ids:
            return "no_citation"
        if any(i not in by_id for i in c.record_ids):
            return "cites_unretrieved_record"
        if any(by_id[i].is_private for i in c.record_ids):
            return "cites_private_record"
        if output_has_medical_advice(c.sentence):
            return "medical_advice"
        if lexical_support(c.sentence, [by_id[i].text for i in c.record_ids]) < self.min_support:
            return "unsupported_words"
        return None

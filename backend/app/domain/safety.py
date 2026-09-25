"""Medical safety rules (NFR-AI-5: zero medical or dosage advice).

A question like "Did I take my morning tablet?" is a lookup in the person's own
log and is allowed. "Can I take two tablets?" asks for advice and is refused
before retrieval ever runs.
"""
import re

MEDICAL_REPLY = (
    "I can't give advice about medicines or doses. Please ask your doctor or your "
    "caregiver. I can tell you what you saved, for example whether you marked a "
    "reminder as done."
)

_MED = re.compile(
    r"\b(medicine|medicines|medication|medications|tablet|tablets|pill|pills|capsule|capsules|"
    r"dose|doses|dosage|insulin|syrup|injection|drug|drugs|mg|paracetamol|crocin|dolo|"
    r"metformin|donepezil|aricept|memantine|rivastigmine|galantamine|aspirin|antibiotic|bp tablet)\b",
    re.I,
)

_ADVICE = re.compile(
    r"\b(how much|how many|should i|shall i|can i|could i|may i|is it (ok|okay|safe|fine|bad)|"
    r"safe to|side effects?|overdose|double|skip|stop taking|stop my|instead of|increase|"
    r"decrease|reduce|mix|with alcohol|what dose|which (medicine|tablet|pill)|what (medicine|tablet|pill) "
    r"(should|to)|good for|recommend)\b",
    re.I,
)

# Output-side check: advice phrasing that must never appear in an answer.
_ADVICE_OUT = re.compile(
    r"\b(you should (take|stop|skip|increase|reduce|double)|you can (take|stop|skip)|"
    r"it is (safe|okay|fine) to (take|stop|skip)|recommended dose|take \d+\s?(mg|tablets?|pills?))\b",
    re.I,
)


def is_medical_advice_request(question: str) -> bool:
    q = question or ""
    if re.search(r"\b(dose|dosage|overdose|side effects?)\b", q, re.I):
        return True
    return bool(_MED.search(q) and _ADVICE.search(q))


def output_has_medical_advice(sentence: str) -> bool:
    return bool(_ADVICE_OUT.search(sentence or ""))

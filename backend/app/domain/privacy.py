"""Keeping personal details away from the language model.

Before any text leaves the server for an external model, the Redactor replaces
names, places and identifiers with neutral tokens such as PERSON_12, PLACE_3 or
PHONE_8f2a. The model only ever sees the tokens. When its reply comes back, the
server puts the real values back. The mapping itself never leaves the server.

Tokens are stable (PERSON_<id>, PLACE_<id>, a short hash for numbers), so the
same memory always produces the same redacted text. That keeps cached
embeddings valid between requests.

Pure Python: no framework, no network, fully unit-tested.
"""
import hashlib
import re
from dataclasses import dataclass, field

# Order matters: longer and more specific patterns run first.
_ID_PATTERNS = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("CARD", re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{1,7}\b")),             # 13-19 digit card numbers
    ("AADHAAR", re.compile(r"\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b")),                  # 12-digit Aadhaar
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),                                  # Indian PAN
    ("PHONE", re.compile(r"(?:\+?91[\s-]?|\b0)?[6-9]\d{4}[\s-]?\d{5}\b")),            # Indian mobile
    ("PHONE", re.compile(r"\b0\d{2,4}[\s-]\d{6,8}\b")),                               # landline with STD code
    ("COORD", re.compile(r"-?\d{1,2}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}")),             # "19.2183, 72.9781"
    ("PINCODE", re.compile(r"\b[1-9]\d{2}\s?\d{3}\b")),                              # 6-digit PIN code
]
_TITLES = {"dr", "mr", "mrs", "ms", "shri", "smt", "kumari", "the", "and", "of", "at", "near"}
_TOKEN_RE = re.compile(r"\b(?:PERSON|FAMILY|PLACE)_\d+\b|\bUSER\b|\b(?:EMAIL|CARD|AADHAAR|PAN|PHONE|COORD|PINCODE)_[0-9a-f]{4}\b")


def _hash4(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:4]


@dataclass
class Redactor:
    """Built per request from the person's own people, places and family names."""
    people: dict[int, str] = field(default_factory=dict)     # person id -> name
    places: dict[int, str] = field(default_factory=dict)     # place id -> name
    family: dict[int, str] = field(default_factory=dict)     # caregiver user id -> name
    user_name: str = ""
    _names: list = field(default_factory=list, init=False)   # (compiled pattern, token, canonical)
    _restore: dict = field(default_factory=dict, init=False)  # token -> surface text seen

    def __post_init__(self):
        entries = []
        for pid, name in self.places.items():
            entries.append((name, f"PLACE_{pid}"))
        for pid, name in self.people.items():
            entries += [(v, f"PERSON_{pid}") for v in self._variants(name)]
        for uid, name in self.family.items():
            entries += [(v, f"FAMILY_{uid}") for v in self._variants(name)]
        if self.user_name:
            entries += [(v, "USER") for v in self._variants(self.user_name)]
        seen, ordered = set(), []
        for value, token in sorted(entries, key=lambda e: -len(e[0])):        # longest first
            key = value.lower()
            if len(key) < 3 or key in seen:
                continue
            seen.add(key)
            ordered.append((re.compile(r"(?<![\w])" + re.escape(value) + r"(?![\w])", re.IGNORECASE), token))
        self._names = ordered

    @staticmethod
    def _variants(name: str) -> list[str]:
        """'Dr. Kulkarni' -> ['Dr. Kulkarni', 'Kulkarni']; 'Ramesh Joshi' -> ['Ramesh Joshi', 'Ramesh', 'Joshi']."""
        name = (name or "").strip()
        if not name:
            return []
        words = [w.strip(".,") for w in name.split()]
        parts = [w for w in words if len(w) >= 3 and w.lower() not in _TITLES]
        return [name] + parts

    def redact(self, text: str) -> str:
        if not text:
            return text
        out = text
        for pattern, token in self._names:
            def _swap(m, token=token):
                self._restore.setdefault(token, m.group(0))
                return token
            out = pattern.sub(_swap, out)
        for kind, pattern in _ID_PATTERNS:
            def _swap_id(m, kind=kind):
                token = f"{kind}_{_hash4(re.sub(r'[^0-9A-Za-z@.]', '', m.group(0)).lower())}"
                self._restore.setdefault(token, m.group(0))
                return token
            out = pattern.sub(_swap_id, out)
        return out

    def restore(self, text: str) -> str:
        """Put real values back into the model's reply. Unknown tokens are left as they are."""
        if not text:
            return text
        return _TOKEN_RE.sub(lambda m: self._restore.get(m.group(0), m.group(0)), text)

    def replacements(self) -> list[dict]:
        """What was hidden, for the privacy preview screen (shown only to the owner)."""
        return [{"token": t, "original": v, "type": t.split("_")[0].lower()} for t, v in self._restore.items()]


def contains_pii(text: str, redactor: Redactor) -> bool:
    """True if redacting would change the text, i.e. it still holds a name, place or identifier."""
    probe = Redactor(redactor.people, redactor.places, redactor.family, redactor.user_name)
    return probe.redact(text) != text


def strip_jpeg_metadata(data: bytes) -> bytes:
    """Remove EXIF (including GPS position), XMP, IPTC and comments from a JPEG. Pixels are untouched.

    Keeps APP0 (JFIF), APP2 (colour profile) and APP14 (Adobe colour transform) so the image looks the same.
    Anything that is not a well-formed JPEG is returned unchanged.
    """
    if not data or not data.startswith(b"\xff\xd8"):
        return data
    out = bytearray(b"\xff\xd8")
    i = 2
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            return data
        marker = data[i + 1]
        if marker == 0xFF:                       # fill byte
            i += 1
            continue
        if marker == 0xDA:                       # start of scan: the rest is image data
            out += data[i:]
            return bytes(out)
        if 0xD0 <= marker <= 0xD9 or marker == 0x01:
            out += data[i:i + 2]
            i += 2
            continue
        length = int.from_bytes(data[i + 2:i + 4], "big")
        if length < 2 or i + 2 + length > n:
            return data
        if marker not in (0xE1, 0xED, 0xFE):     # drop APP1 (EXIF/XMP), APP13 (IPTC), COM
            out += data[i:i + 2 + length]
        i += 2 + length
    return bytes(out)

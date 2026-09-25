"""Text utilities used by retrieval and the GroundingGuard.

Pure Python on purpose: the domain layer imports no framework or SDK,
so everything here is unit-testable on a laptop with no network.
"""
import math
import re
import zlib

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "of", "to", "in", "on", "at", "by",
    "for", "with", "from", "about", "into", "over", "after", "before", "up", "down", "out", "off",
    "is", "am", "are", "was", "were", "be", "been", "being", "i", "me", "my", "mine", "myself",
    "you", "your", "yours", "we", "our", "us", "he", "him", "his", "she", "her", "hers", "it",
    "its", "they", "them", "their", "this", "that", "these", "those", "there", "here", "what",
    "who", "whom", "whose", "which", "when", "where", "why", "how", "much", "many", "any", "some",
    "all", "no", "not", "yes", "do", "does", "did", "done", "doing", "have", "has", "had", "will",
    "would", "can", "could", "should", "shall", "may", "might", "must", "s", "t", "d", "ll", "ve",
    "re", "m", "just", "also", "very", "too", "again", "ever", "yet", "still", "please", "tell",
}

# Irregular verb forms mapped to their base form before stemming.
LEMMAS = {
    "met": "meet", "saw": "see", "seen": "see", "went": "go", "gone": "go", "ate": "eat",
    "eaten": "eat", "bought": "buy", "kept": "keep", "took": "take", "taken": "take",
    "gave": "give", "given": "give", "told": "tell", "left": "leave", "won": "win",
    "made": "make", "brought": "bring", "came": "come", "said": "say", "got": "get",
    "found": "find", "paid": "pay", "wrote": "write", "written": "write", "sat": "sit",
    "spoke": "speak", "thought": "think", "felt": "feel", "children": "child", "men": "man",
    "women": "woman", "spent": "spend", "lost": "lose", "put": "put", "ran": "run",
}

# Words that carry no "what is this question about" signal once the time
# filter has run. A memory must share the question's other content words.
GENERIC_WORDS = """
go meet see get put keep say come make eat buy have give know want like thing things day time
today yesterday morning evening night week month year last ago name take bring find happen
happened remember memory memories save saved note noted write wrote do anything something
someone anyone people person place places whom
""".split()


def stem(word: str) -> str:
    """Tiny suffix stripper. Consistent, not linguistically perfect."""
    w = word
    if len(w) <= 3:
        return w
    if w.endswith("ing") and len(w) - 3 >= 3:
        w = w[:-3]
    elif w.endswith("ed") and len(w) - 2 >= 3:
        w = w[:-2]
    elif w.endswith(("sses", "xes", "zes", "ches", "shes")):
        w = w[:-2]
    elif w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    if w.endswith("e") and len(w) > 3:
        w = w[:-1]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "lsz":
        w = w[:-1]
    return w


# Stemmed once at import so the set matches what content_tokens() produces.
GENERIC = {stem(LEMMAS.get(w, w)) for w in GENERIC_WORDS}

_WORD = re.compile(r"[a-z0-9\u0900-\u097f]+")


def tokenize(text: str) -> list[str]:
    tokens = []
    for raw in _WORD.findall((text or "").lower()):
        base = LEMMAS.get(raw, raw)
        tokens.append(stem(base))
    return tokens


def content_tokens(text: str) -> list[str]:
    out = []
    for raw in _WORD.findall((text or "").lower()):
        if raw in STOPWORDS:
            continue
        base = LEMMAS.get(raw, raw)
        if base in STOPWORDS:
            continue
        out.append(stem(base))
    return out


def focus_terms(question: str) -> set[str]:
    """Content words that say what the question is about (minus generic verbs/time words)."""
    return {t for t in content_tokens(question) if t not in GENERIC and len(t) > 1}


def focus_coverage_ok(focus: set[str], doc_tokens: set[str]) -> bool:
    """A memory is eligible only if it shares enough of the question's focus words.
    1-2 focus words: all must match. 3+: at least half."""
    if not focus:
        return True
    hits = len(focus & doc_tokens)
    need = len(focus) if len(focus) <= 2 else math.ceil(len(focus) / 2)
    return hits >= need


def proper_nouns(question: str) -> set[str]:
    """Capitalised words that are not the first word and not stopwords, e.g. 'Goa', 'Kusum'."""
    words = re.findall(r"[A-Za-z][A-Za-z']+", question or "")
    out = set()
    for i, w in enumerate(words):
        clean = w.split("'")[0]
        if i == 0 or not clean[:1].isupper() or clean.lower() in STOPWORDS or clean == "I":
            continue
        out.add(stem(LEMMAS.get(clean.lower(), clean.lower())))
    return out


def hashed_embedding(text: str, dim: int = 2048) -> dict[int, float]:
    """Sparse bag-of-words + bigram vector using a stable hash (crc32, not Python's hash())."""
    toks = content_tokens(text)
    feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    vec: dict[int, float] = {}
    for f in feats:
        idx = zlib.crc32(f.encode("utf-8")) % dim
        vec[idx] = vec.get(idx, 0.0) + (1.0 if "_" not in f else 0.5)
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def sparse_cosine(a: dict, b: dict) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def dense_cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)

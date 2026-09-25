"""Language-model providers behind one small interface.

OfflineProvider needs no key and no network: hashed bag-of-words retrieval and
answers built only by quoting the person's own memories. It keeps the demo and
the tests working when there is no internet or the free API quota runs out.

GeminiProvider uses Google's Gemini API (free tier via AI Studio) for semantic
embeddings, fluent answers, a second verification pass, voice transcription and
photo captions. The client app never sees the key: only this backend calls it.
"""
import base64
import json
import re
from functools import lru_cache

import httpx

from ..config import settings
from ..domain.grounding import Claim
from ..domain.text import dense_cosine, hashed_embedding, sparse_cosine


class ProviderError(Exception):
    pass


class OfflineProvider:
    name = "offline"
    embed_name = "offline-hash-2048"
    lexical_focus = True  # require the question's focus words to appear in the memory
    min_score = 0.12
    relative = 0.80
    verifier = None

    def embed_docs(self, texts):
        return [hashed_embedding(t) for t in texts]

    def embed_query(self, text):
        return hashed_embedding(text)

    def similarity(self, a, b):
        return sparse_cosine(a, b)

    def generate_claims(self, question, items, max_items=3):
        """Quote the best memories. Nothing is paraphrased, so nothing can be invented."""
        claims = []
        for it in items[:max_items]:
            where = f" at {it['place']}" if it.get("place") else ""
            verb = "your log says" if it.get("kind") == "log" else "you saved"
            text = it["memory"].rstrip(".")
            claims.append(Claim(sentence=f"On {it['when']}{where}, {verb}: \u201c{text}.\u201d", record_ids=[it["id"]]))
        return claims

    def transcribe(self, data: bytes, mime: str):
        return None

    def caption(self, data: bytes, mime: str):
        return None


SYSTEM_PROMPT = """You help an older person with memory loss recall their OWN saved memories.
Rules:
- Use ONLY the memories given. Never add a fact, name, time or place that is not written in them.
- Never give medical advice, names of medicines to take, or doses.
- Talk to the person as "you". Use short, simple sentences. At most 3 sentences.
- Every sentence must list the ids of the memories that support it.
- If the memories do not answer the question, set answer_found to false and return no claims.
Return JSON only: {"answer_found": true|false, "claims": [{"sentence": "...", "record_ids": [1, 2]}]}"""

VERIFY_PROMPT = """For each item, answer whether the SENTENCE is fully supported by the MEMORIES text
(every fact in the sentence must be stated in the memories). Return JSON only:
{"verdicts": [true, false, ...]} in the same order as the items."""


class GeminiProvider:
    lexical_focus = False
    relative = 0.90
    BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, key: str):
        self.model = settings.GEMINI_MODEL
        self.embed_model = settings.GEMINI_EMBED_MODEL
        self.min_score = settings.GEMINI_MIN_SCORE
        self.name = f"gemini:{self.model}"
        self.embed_name = f"gemini:{self.embed_model}:768"
        self.client = httpx.Client(timeout=25.0, headers={"x-goog-api-key": key})

    def _post(self, path: str, body: dict) -> dict:
        try:
            r = self.client.post(f"{self.BASE}/{path}", json=body)
        except httpx.HTTPError as e:
            raise ProviderError(f"network: {e}") from e
        if r.status_code != 200:
            raise ProviderError(f"gemini {r.status_code}: {r.text[:200]}")
        return r.json()

    def _generate(self, system: str, parts: list, json_mode: bool = True) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.1, **({"responseMimeType": "application/json"} if json_mode else {})},
        }
        data = self._post(f"models/{self.model}:generateContent", body)
        try:
            return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError) as e:
            raise ProviderError("empty response") from e

    @staticmethod
    def _json(text: str) -> dict:
        text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.M).strip()
        return json.loads(text)

    def _embed(self, texts, task):
        out = []
        for i in range(0, len(texts), 90):
            chunk = texts[i:i + 90]
            reqs = [{"model": f"models/{self.embed_model}", "content": {"parts": [{"text": t[:2000]}]},
                     "taskType": task, "outputDimensionality": 768} for t in chunk]
            data = self._post(f"models/{self.embed_model}:batchEmbedContents", {"requests": reqs})
            out.extend(e["values"] for e in data.get("embeddings", []))
        if len(out) != len(texts):
            raise ProviderError("embedding count mismatch")
        return out

    def embed_docs(self, texts):
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text):
        return self._embed([text], "RETRIEVAL_QUERY")[0]

    def similarity(self, a, b):
        return dense_cosine(a, b)

    def generate_claims(self, question, items, max_items=6):
        memories = [{"id": it["id"], "when": it["when"], "place": it.get("place") or "",
                     "people": it.get("people", []), "memory": it["memory"]} for it in items]
        prompt = f"QUESTION: {question}\n\nMEMORIES:\n{json.dumps(memories, ensure_ascii=False)}"
        try:
            data = self._json(self._generate(SYSTEM_PROMPT, [{"text": prompt}]))
        except json.JSONDecodeError as e:
            raise ProviderError("model did not return JSON") from e
        if not data.get("answer_found"):
            return []
        claims = []
        for c in data.get("claims", []):
            ids = [int(i) for i in c.get("record_ids", []) if str(i).isdigit()]
            claims.append(Claim(sentence=str(c.get("sentence", "")).strip(), record_ids=ids))
        return claims

    def verifier(self, pairs):
        items = [{"sentence": s, "memories": texts} for s, texts in pairs]
        data = self._json(self._generate(VERIFY_PROMPT, [{"text": json.dumps(items, ensure_ascii=False)}]))
        verdicts = [bool(v) for v in data.get("verdicts", [])]
        return verdicts if len(verdicts) == len(pairs) else [True] * len(pairs)

    def _media(self, data: bytes, mime: str, instruction: str):
        parts = [{"inline_data": {"mime_type": mime.split(";")[0], "data": base64.b64encode(data).decode()}},
                 {"text": instruction}]
        return self._generate("You describe a person's own diary media plainly and briefly.", parts,
                              json_mode=False).strip()

    def transcribe(self, data: bytes, mime: str):
        return self._media(data, mime, "Transcribe this voice note exactly. If it is in Hindi or Marathi, write it "
                                       "in that language, then an English translation in brackets. "
                                       "Return only the transcript.")

    def caption(self, data: bytes, mime: str):
        return self._media(data, mime, "Describe this photo in one plain sentence for a memory diary. "
                                       "Say what is visible. Do not guess anyone's name.")


@lru_cache
def get_provider():
    mode = settings.LLM_PROVIDER
    if mode == "gemini" or (mode == "auto" and settings.GEMINI_API_KEY):
        return GeminiProvider(settings.GEMINI_API_KEY)
    return OfflineProvider()


@lru_cache
def get_offline():
    return OfflineProvider()

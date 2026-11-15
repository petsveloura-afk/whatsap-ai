"""Free local near-duplicate detection: hashed character-trigram vectors + cosine.
No API, no pgvector required (works on SQLite and Postgres)."""
import hashlib, math, re
DIM = 256

def embed(text: str) -> list[float]:
    t = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()
    v = [0.0] * DIM
    for i in range(max(len(t) - 2, 0)):
        h = int.from_bytes(hashlib.blake2b(t[i:i + 3].encode(), digest_size=4).digest(), "big")
        v[h % DIM] += 1.0 if (h >> 31) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]

def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))

def is_near_duplicate(text: str, others: list[str], threshold: float = 0.95) -> bool:
    e = embed(text)
    return any(cosine(e, embed(o)) >= threshold for o in others)

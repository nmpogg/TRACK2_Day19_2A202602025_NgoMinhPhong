"""Minimal hybrid-memory POC: lexical + vector recall and online features."""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TOKEN_RE = re.compile(r"\w+", re.UNICODE)
DIM = 256


@dataclass
class Memory:
    memory_id: str
    user_id: str
    text: str
    created_at: datetime
    vector: np.ndarray


class HybridMemoryAgent:
    """In-process POC mirroring Qdrant payload filters and Feast online lookup.

    Hash embeddings keep the demo deterministic and offline. In production the
    same interface uses a multilingual embedding model and Qdrant upserts.
    """

    def __init__(self) -> None:
        self.memories: list[Memory] = []
        self.recent_queries: dict[str, list[str]] = defaultdict(list)
        self.profile_fallback = {
            "u_001": {
                "preferred_language": "vi/en mix",
                "reading_speed_wpm": 187,
                "topic_affinity": "cloud",
                "queries_last_hour": 4,
            }
        }

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return TOKEN_RE.findall(text.casefold())

    @classmethod
    def _embed(cls, text: str) -> np.ndarray:
        """Feature-hash word and character n-grams into a normalized vector."""
        vector = np.zeros(DIM, dtype=np.float32)
        normalized = " ".join(cls._tokens(text))
        features = cls._tokens(text)
        features += [normalized[i:i + 3] for i in range(max(0, len(normalized) - 2))]
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            raw = int.from_bytes(digest, "little")
            vector[raw % DIM] += 1.0 if raw & 1 else -1.0
        norm = float(np.linalg.norm(vector))
        return vector / norm if norm else vector

    def remember(self, text: str, user_id: str = "u_001") -> None:
        """Chunk text by paragraph, embed it, and upsert user-scoped memories."""
        chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
        for chunk in chunks:
            memory_id = hashlib.sha1(
                f"{user_id}:{chunk}".encode("utf-8"), usedforsecurity=False
            ).hexdigest()[:12]
            # Idempotent upsert, equivalent to a Qdrant point ID replacement.
            self.memories = [m for m in self.memories if m.memory_id != memory_id]
            self.memories.append(Memory(
                memory_id, user_id, chunk, datetime.now(timezone.utc), self._embed(chunk)
            ))

    def _profile(self, user_id: str) -> dict:
        """Read Feast online features when available; otherwise use demo data."""
        try:
            from feast import FeatureStore
            store = FeatureStore(repo_path=str(ROOT / "app" / "feast_repo"))
            result = store.get_online_features(
                features=[
                    "user_profile_features:preferred_language",
                    "user_profile_features:reading_speed_wpm",
                    "user_profile_features:topic_affinity",
                    "query_velocity_features:queries_last_hour",
                ],
                entity_rows=[{"user_id": user_id}],
            ).to_dict()
            profile = {key: values[0] for key, values in result.items() if values}
            if profile.get("topic_affinity") is not None:
                return profile
        except Exception:
            pass
        return self.profile_fallback.get(user_id, {
            "preferred_language": "vi", "reading_speed_wpm": 200,
            "topic_affinity": "unknown", "queries_last_hour": 0,
        })

    def _hybrid_hits(self, query: str, user_id: str, top_k: int = 3) -> list[Memory]:
        candidates = [m for m in self.memories if m.user_id == user_id]
        if not candidates:
            return []
        query_tokens = Counter(self._tokens(query))
        query_vector = self._embed(query)
        lexical = []
        semantic = []
        for memory in candidates:
            words = Counter(self._tokens(memory.text))
            lexical.append(sum(min(count, words[token]) for token, count in query_tokens.items()))
            semantic.append(float(np.dot(query_vector, memory.vector)))
        kw_rank = sorted(range(len(candidates)), key=lambda i: lexical[i], reverse=True)
        vec_rank = sorted(range(len(candidates)), key=lambda i: semantic[i], reverse=True)
        scores = defaultdict(float)
        for ranking in (kw_rank, vec_rank):
            for rank, index in enumerate(ranking, 1):
                scores[index] += 1.0 / (60 + rank)
        ordered = sorted(scores, key=scores.get, reverse=True)[:top_k]
        return [candidates[index] for index in ordered]

    def recall(self, query: str, user_id: str = "u_001") -> str:
        """Return profile, recent activity and top user-filtered hybrid memories."""
        profile = self._profile(user_id)
        previous = self.recent_queries[user_id][-5:]
        hits = self._hybrid_hits(query, user_id)
        self.recent_queries[user_id].append(query)
        memory_text = "\n".join(f"  {i}. {m.text}" for i, m in enumerate(hits, 1))
        recent = "; ".join(previous) if previous else "chưa có query trước đó trong phiên"
        return (
            f"User profile: language={profile.get('preferred_language')}, "
            f"topic_affinity={profile.get('topic_affinity')}, "
            f"reading_speed={profile.get('reading_speed_wpm')} wpm.\n"
            f"Recent activity: queries_last_hour={profile.get('queries_last_hour', 0)}; "
            f"session_queries={recent}.\nTop memories:\n{memory_text or '  (không tìm thấy)'}"
        )

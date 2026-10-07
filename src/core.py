"""Cache and source-snapshot logic shared by the API and tests.

The naive key is intentionally wrong. Keep it only to reproduce the failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Protocol


DOCUMENT_KEY = "citation-demo:source-snapshot"
ANSWER_GENERATOR_VERSION = "extractive-v1"
STOP_WORDS = {"a", "an", "are", "do", "does", "for", "in", "is", "the", "to", "what", "when"}
INITIAL_DOCUMENTS = {
    "harbor-policy": "Harbor permits expire after 30 days.",
    "museum-policy": "Museum tickets are refundable within 14 days.",
}


class Cache(Protocol):
    def get(self, name: str) -> str | None: ...

    def set(
        self, name: str, value: str, *, ex: int | None = None, nx: bool = False
    ) -> object: ...


@dataclass(frozen=True)
class Snapshot:
    documents: dict[str, str]
    version: str


def document_version(documents: dict[str, str]) -> str:
    canonical = json.dumps(documents, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def encode_snapshot(documents: dict[str, str]) -> str:
    return json.dumps(
        {"version": document_version(documents), "documents": documents},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def read_snapshot(cache: Cache) -> Snapshot:
    raw = cache.get(DOCUMENT_KEY)
    if raw is None:
        cache.set(DOCUMENT_KEY, encode_snapshot(INITIAL_DOCUMENTS), nx=True)
        raw = cache.get(DOCUMENT_KEY)
    if raw is None:
        raise RuntimeError("Could not initialize the source snapshot")
    record = json.loads(raw)
    documents = record["documents"]
    if not isinstance(documents, dict) or record["version"] != document_version(documents):
        raise ValueError("Source snapshot/version mismatch")
    return Snapshot(documents=documents, version=record["version"])


def replace_document(cache: Cache, doc_id: str, text: str) -> Snapshot:
    # This compact demo assumes one writer. Production updates need a Redis
    # transaction or an external source-of-truth with the same snapshot rule.
    current = read_snapshot(cache)
    if doc_id not in current.documents:
        raise KeyError(doc_id)
    updated = {**current.documents, doc_id: text}
    cache.set(DOCUMENT_KEY, encode_snapshot(updated))
    return Snapshot(documents=updated, version=document_version(updated))


def normalize_question(question: str) -> str:
    return " ".join(question.casefold().split())


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.casefold()) if token not in STOP_WORDS}


def generate_answer(question: str, snapshot: Snapshot) -> dict[str, object]:
    terms = _tokens(question)
    ranked = sorted(
        ((-len(terms & _tokens(body)), doc_id, body) for doc_id, body in snapshot.documents.items())
    )
    if not terms or not ranked or ranked[0][0] == 0:
        return {"answer": "No matching source found.", "citation": None}
    _, doc_id, excerpt = ranked[0]
    return {
        "answer": f"The source says: {excerpt}",
        "citation": {"document_id": doc_id, "excerpt": excerpt},
    }


def citation_is_current(citation: object, snapshot: Snapshot) -> bool:
    if not isinstance(citation, dict):
        return False
    doc_id = citation.get("document_id")
    excerpt = citation.get("excerpt")
    return isinstance(doc_id, str) and isinstance(excerpt, str) and excerpt in snapshot.documents.get(doc_id, "")


def cache_key(question: str, mode: str, snapshot_version: str) -> str:
    if mode not in {"naive", "versioned"}:
        raise ValueError("mode must be naive or versioned")
    question_hash = sha256(normalize_question(question).encode("utf-8")).hexdigest()
    # The naive variant omits the source version on purpose.
    version_part = snapshot_version if mode == "versioned" else "unversioned"
    return f"citation-demo:answer:{mode}:{ANSWER_GENERATOR_VERSION}:{version_part}:{question_hash}"


class AnswerService:
    def __init__(self, cache: Cache, ttl_seconds: int = 60):
        if not 1 <= ttl_seconds <= 3600:
            raise ValueError("CACHE_TTL_SECONDS must be between 1 and 3600")
        self.cache = cache
        self.ttl_seconds = ttl_seconds

    def answer(self, question: str, mode: str = "versioned") -> dict[str, object]:
        if not question.strip():
            raise ValueError("question must not be blank")
        snapshot = read_snapshot(self.cache)
        key = cache_key(question, mode, snapshot.version)
        cached = self.cache.get(key)
        if cached is None:
            result = generate_answer(question, snapshot)
            self.cache.set(key, json.dumps(result, ensure_ascii=False), ex=self.ttl_seconds)
            hit = False
        else:
            result = json.loads(cached)
            hit = True
        return {
            **result,
            "cache_hit": hit,
            "source_version": snapshot.version,
            "citation_valid": citation_is_current(result["citation"], snapshot),
        }

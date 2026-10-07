"""Deterministic tests; no Dragonfly server or LLM key is required."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from src.app import create_app
from src.core import (
    AnswerService,
    DOCUMENT_KEY,
    cache_key,
    document_version,
    read_snapshot,
    replace_document,
)


QUESTION = "When do harbor permits expire?"


class FakeClockCache:
    def __init__(self) -> None:
        self.now = 0
        self.values: dict[str, tuple[str, int | None]] = {}

    def get(self, name: str) -> str | None:
        entry = self.values.get(name)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and expires_at <= self.now:
            del self.values[name]
            return None
        return value

    def set(self, name: str, value: str, *, ex: int | None = None, nx: bool = False) -> bool:
        if nx and self.get(name) is not None:
            return False
        self.values[name] = (value, self.now + ex if ex is not None else None)
        return True


class CacheBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = FakeClockCache()
        self.service = AnswerService(self.cache, ttl_seconds=5)

    def test_naive_key_reuses_stale_citation_until_ttl_expires(self) -> None:
        first = self.service.answer(QUESTION, mode="naive")
        self.assertFalse(first["cache_hit"])
        self.assertTrue(first["citation_valid"])
        self.assertIn("30 days", first["answer"])

        repeat = self.service.answer(QUESTION, mode="naive")
        self.assertTrue(repeat["cache_hit"])

        replace_document(self.cache, "harbor-policy", "Harbor permits expire after 45 days.")
        stale = self.service.answer(QUESTION, mode="naive")
        self.assertTrue(stale["cache_hit"])
        self.assertFalse(stale["citation_valid"])
        self.assertIn("30 days", stale["answer"])

        self.cache.now += 5
        refreshed = self.service.answer(QUESTION, mode="naive")
        self.assertFalse(refreshed["cache_hit"])
        self.assertTrue(refreshed["citation_valid"])
        self.assertIn("45 days", refreshed["answer"])

    def test_versioned_key_misses_after_edit_and_preserves_valid_citation(self) -> None:
        first = self.service.answer(QUESTION)
        self.assertFalse(first["cache_hit"])
        self.assertTrue(self.service.answer(QUESTION)["cache_hit"])

        replace_document(self.cache, "harbor-policy", "Harbor permits expire after 45 days.")
        changed = self.service.answer(QUESTION)
        self.assertFalse(changed["cache_hit"])
        self.assertNotEqual(first["source_version"], changed["source_version"])
        self.assertTrue(changed["citation_valid"])
        self.assertIn("45 days", changed["answer"])
        self.assertTrue(self.service.answer(QUESTION)["cache_hit"])

    def test_no_matching_document_has_no_citation(self) -> None:
        result = self.service.answer("How tall is the rocket?")
        self.assertIsNone(result["citation"])
        self.assertFalse(result["citation_valid"])
        self.assertEqual(result["answer"], "No matching source found.")

    def test_cache_entry_has_bounded_ttl_but_source_snapshot_does_not(self) -> None:
        self.service.answer(QUESTION)
        answer_keys = [key for key in self.cache.values if key != DOCUMENT_KEY]
        self.assertEqual(len(answer_keys), 1)
        self.assertEqual(self.cache.values[answer_keys[0]][1], 5)
        self.assertIsNone(self.cache.values[DOCUMENT_KEY][1])
        self.cache.now = 6
        self.assertIsNone(self.cache.get(answer_keys[0]))
        self.assertIsNotNone(self.cache.get(DOCUMENT_KEY))

    def test_question_normalization_and_generator_version_are_in_key(self) -> None:
        version = read_snapshot(self.cache).version
        first = cache_key("  When   do HARBOR permits expire?  ", "versioned", version)
        second = cache_key(QUESTION, "versioned", version)
        self.assertEqual(first, second)
        self.assertIn("extractive-v1", first)

    def test_tampered_source_version_is_rejected(self) -> None:
        read_snapshot(self.cache)
        self.cache.set(DOCUMENT_KEY, '{"documents":{"a":"text"},"version":"wrong"}')
        with self.assertRaises(ValueError):
            read_snapshot(self.cache)

    def test_ttl_outside_supported_range_is_rejected(self) -> None:
        for ttl in (0, 3601):
            with self.subTest(ttl=ttl), self.assertRaises(ValueError):
                AnswerService(self.cache, ttl_seconds=ttl)

    def test_document_version_is_stable_across_dictionary_order(self) -> None:
        self.assertEqual(document_version({"a": "x", "b": "y"}), document_version({"b": "y", "a": "x"}))


class HttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(cache=FakeClockCache(), ttl_seconds=10))

    def test_endpoint_reproduces_and_fixes_stale_citation(self) -> None:
        first = self.client.get("/answer", params={"question": QUESTION, "mode": "naive"})
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["citation_valid"])

        update = self.client.put("/documents/harbor-policy", json={"text": "Harbor permits expire after 45 days."})
        self.assertEqual(update.status_code, 200)

        naive = self.client.get("/answer", params={"question": QUESTION, "mode": "naive"}).json()
        corrected = self.client.get("/answer", params={"question": QUESTION, "mode": "versioned"}).json()
        self.assertTrue(naive["cache_hit"])
        self.assertFalse(naive["citation_valid"])
        self.assertFalse(corrected["cache_hit"])
        self.assertTrue(corrected["citation_valid"])

    def test_unknown_document_is_404(self) -> None:
        response = self.client.put("/documents/unknown", json={"text": "New text"})
        self.assertEqual(response.status_code, 404)

    def test_invalid_mode_is_rejected(self) -> None:
        response = self.client.get("/answer", params={"question": QUESTION, "mode": "other"})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()

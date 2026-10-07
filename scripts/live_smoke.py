"""Exercise the HTTP demo against a fresh, local Dragonfly instance.

This script writes demo keys. Run it only against an empty disposable instance.
"""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from redis import Redis

from src.app import create_app
from src.core import DOCUMENT_KEY


QUESTION = "When do harbor permits expire?"


def main() -> None:
    url = os.getenv("DRAGONFLY_URL", "redis://localhost:6379/0")
    if urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Live smoke test accepts only a local, disposable server")

    cache = Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
    cache.ping()
    if cache.get(DOCUMENT_KEY) is not None:
        raise SystemExit("Demo source key already exists; use a fresh disposable server")

    with TestClient(create_app(cache=cache, ttl_seconds=60)) as client:
        def answer(mode: str) -> dict[str, object]:
            response = client.get("/answer", params={"question": QUESTION, "mode": mode})
            response.raise_for_status()
            return response.json()

        original = answer("naive")
        repeated = answer("naive")
        update = client.put(
            "/documents/harbor-policy", json={"text": "Harbor permits expire after 45 days."}
        )
        update.raise_for_status()
        stale = answer("naive")
        corrected = answer("versioned")
        corrected_repeat = answer("versioned")

    checks = {
        "initial_answer_30_days": "30 days" in original["answer"],
        "naive_repeat_is_hit": repeated["cache_hit"] is True,
        "naive_after_edit_is_stale": stale["cache_hit"] is True
        and stale["citation_valid"] is False
        and "30 days" in stale["answer"],
        "versioned_after_edit_is_fresh": corrected["cache_hit"] is False
        and corrected["citation_valid"] is True
        and "45 days" in corrected["answer"],
        "versioned_repeat_is_hit": corrected_repeat["cache_hit"] is True,
    }
    print(json.dumps({"checks": checks, "passed": all(checks.values())}, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

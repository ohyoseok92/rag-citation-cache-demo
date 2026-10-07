# Stale RAG citations: a small Dragonfly + FastAPI demo

This original, synthetic example reproduces a citation correctness bug. An answer is cached for “When do harbor permits expire?”; the cited document changes from **30 days** to **45 days**; a naive key returns the old answer until its TTL expires. The corrected key includes a hash of the complete source snapshot and misses immediately after the edit.

There is no LLM call or external document. The “answer generator” picks the document with the most question-word overlap and quotes its full text. It exists to make cache behavior reproducible, not to demonstrate answer quality or retrieval performance.

## Run locally

1. Start Dragonfly, following its [official Windows Docker guidance](https://www.dragonflydb.io/docs/getting-started/docker):

   ```sh
   docker run --rm --name citation-dragonfly -p 127.0.0.1:6379:6379 --ulimit memlock=-1 docker.dragonflydb.io/dragonflydb/dragonfly
   ```

2. In a second terminal, create a Python environment and install dependencies:

   ```sh
   python -m venv .venv
   # Windows PowerShell: .venv\Scripts\Activate.ps1
   # macOS/Linux: source .venv/bin/activate
   python -m pip install -r requirements.txt
   python -m uvicorn src.app:app --reload --host 127.0.0.1 --port 8000
   ```

   The default connection is `redis://localhost:6379/0`. Override it with `DRAGONFLY_URL`. Answer TTL defaults to 60 seconds; set `CACHE_TTL_SECONDS` to a whole number from 1 through 3600.

3. Request an answer, edit the document, then compare modes:

   ```sh
   curl "http://127.0.0.1:8000/answer?question=When%20do%20harbor%20permits%20expire%3F&mode=naive"
   curl -X PUT "http://127.0.0.1:8000/documents/harbor-policy" -H "Content-Type: application/json" -d '{"text":"Harbor permits expire after 45 days."}'
   curl "http://127.0.0.1:8000/answer?question=When%20do%20harbor%20permits%20expire%3F&mode=naive"
   curl "http://127.0.0.1:8000/answer?question=When%20do%20harbor%20permits%20expire%3F&mode=versioned"
   ```

   In PowerShell, use `curl.exe` for those shell commands. The second naive response should have `cache_hit: true`, `citation_valid: false`, and the old 30-day answer. The versioned response should have `cache_hit: false`, `citation_valid: true`, and the new 45-day answer. Run these steps before the answer TTL expires. `GET /documents` shows the current source texts and snapshot hash.

## Test without a server

```sh
python -m unittest discover -s tests -v
```

The tests inject a small fake clock/cache and check the stale answer, immediate versioned miss, TTL expiry, absent citation, invalid source hash, and HTTP behavior. They do **not** prove a live Dragonfly connection.

For a fresh disposable local Dragonfly instance, run `python -m scripts.live_smoke` after installing the requirements. It makes real Redis-protocol requests through the FastAPI endpoints and aborts if the demo source key already exists. It never clears an existing database.

The live smoke test passed on Dragonfly `df-v2.0.0` on 2026-10-08 (Korea time): a repeated naive answer hit the cache, remained stale after a source edit, and carried an invalid citation; the versioned answer missed after the edit, cited the new source, and hit on repetition. This verifies this small behavior on one local server, not production reliability or throughput.

## How the cache stays tied to its source

Dragonfly stores the synthetic source documents and their SHA-256 content hash in one JSON value. A `GET` obtains that snapshot. The corrected answer key includes its hash, a normalized-question hash, and the generator version. A document edit writes a new source snapshot, so the next answer request uses a new key. Old answer keys expire after the bounded TTL. The naive mode deliberately omits the source hash.

The source update endpoint has no authentication and is for localhost only. Updates use a read-modify-write sequence intended for one writer; simultaneous writers need a transaction or another atomic source-update mechanism. A real ingest pipeline must update the source snapshot for every document change, and production retrieval must search only the same snapshot used in the key. TTL alone cannot guarantee citation correctness. The demo makes no performance claim.

This code uses the Redis-compatible Python client supported by [Dragonfly](https://www.dragonflydb.io/docs) and a TTL-bearing [Redis `SET`](https://redis.io/docs/latest/commands/set/) for answer entries.

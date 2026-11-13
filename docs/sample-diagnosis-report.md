# Sample citation diagnosis report

> This is my own synthetic example. It is not a client engagement, production incident, or performance benchmark. It shows the format of a bounded diagnostic handoff.

## Case and acceptance criteria

The synthetic source document originally says, “Harbor permits expire after 30 days.” It is then changed to 45 days. The same question still returns the old answer and citation while its cached answer is alive.

- Reproduction question: `When do harbor permits expire?`
- Trace scope: source snapshot, answer-cache key, returned answer, and cited excerpt. This example uses two synthetic documents and one question.
- Acceptance criterion: immediately after the source edit, the same question returns the 45-day statement and cites text present in the current source. A repeat request may hit the new version's answer cache.

## Observed trace

| Step | Observation | Result |
| --- | --- | --- |
| 1. Ask against the original source | 30-day answer; first request misses the answer cache | Correct for the original source |
| 2. Replace the source text | The source-snapshot version changes | Edit recorded |
| 3. Ask again with the naive key | Cache hit; answer and citation still say 30 days; `citation_valid=false` | Failure reproduced |
| 4. Ask with the versioned key | Cache miss; answer and citation say 45 days; `citation_valid=true` | Fix works for this case |
| 5. Repeat with the versioned key | Cache hit for the 45-day answer; citation stays valid | Repeat behavior checked |

The sequence is covered by the [public regression tests](https://github.com/ohyoseok92/rag-citation-cache-demo/blob/main/tests/test_demo.py) and illustrated in the [browser walkthrough](https://rag-citation-lab-oh6428.oh6428.chatgpt.site/). The browser walkthrough uses an in-page JavaScript cache. It does not call the Python API, Dragonfly, or an LLM.

## Root cause and bounded change

The naive answer key contains the normalized question and answer-generator version but omits the source version. Editing a document therefore leaves the key unchanged. Until the answer entry expires, the cache can return text from the old document even though the current source no longer contains the cited excerpt.

The corrected example includes a SHA-256 hash of the complete, canonically ordered source snapshot in the answer key. A document edit changes the hash, so the next answer request misses the old entry. The service also checks whether the cited excerpt occurs in the current snapshot. The implementation is in the [cache and snapshot module](https://github.com/ohyoseok92/rag-citation-cache-demo/blob/main/src/core.py).

## Handoff checks

1. Ask the question once before editing so the old answer is cached.
2. Edit the document under the same document ID, then immediately ask the same question again.
3. Compare the returned document ID and excerpt with the current source snapshot.
4. Repeat the question to verify that the new version's cached answer remains current.
5. Check answer-entry expiry separately from source-snapshot persistence.

Eleven unit and HTTP tests passed in the local virtual environment on 2026-11-13. These tests use an injected fake clock and cache; they do not establish live-server concurrency, retrieval quality, latency, or production reliability. The repository [README](https://github.com/ohyoseok92/rag-citation-cache-demo#test-without-a-server) records a separate, earlier local Dragonfly smoke test.

## What a real client case would require

This demo makes no LLM call. Its answer generator selects a synthetic document by word overlap and quotes it. For a real RAG system, I would need a redacted failing question, old and current source passages, retrieved chunks or a safe trace, cache behavior, and the agreed test environment. I would then locate whether the mismatch enters during ingestion, indexing, retrieval, answer caching, generation, or citation display.

All document-update paths must advance the version used by the answer cache. Retrieval and displayed citations must refer to the same source snapshot. Concurrent document edits need an atomic update mechanism. The passing synthetic test alone cannot prove that a client's chatbot is accurate. A client handoff would record the actual reproduced failure, feasible change, retest result, and remaining risks for the agreed scope.

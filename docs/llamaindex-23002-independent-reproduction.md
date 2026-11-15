# Independent reproduction: LlamaIndex ingestion source identity

The original discovery and root-cause analysis belong to [vasilisnasopoulos in LlamaIndex issue #23002](https://github.com/run-llama/llama_index/issues/23002). I independently ran two small, offline reproductions on 2026-11-15. This is an open-source issue reproduction, **not** a client engagement, a paid delivery, or a test of a production chatbot.

## Run locally

With Python 3.11 and `uv` installed, from this repository's root:

```sh
uv run --no-project --with llama-index-core==0.14.26 python examples/llamaindex-23002/reproduce_deletion.py
uv run --no-project --with llama-index-core==0.14.26 python examples/llamaindex-23002/reproduce_cache_identity.py
```

The scripts use `MockEmbedding`, `SimpleDocumentStore`, and `SimpleVectorStore` where needed. They make no external model calls and require no customer data. Each asserts its observed behavior and prints `checks: passed` when its checks hold.

## Result 1: a removed document stays in storage

The first run ingests `source_A` and `source_B`, then re-ingests only `source_B` using `UPSERTS_AND_DELETE`.

| First-run content | Expected after re-ingesting B | Observed docstore and vector source IDs |
| --- | --- | --- |
| A and B contain the same text | B only | A and B |
| A and B contain different text | B only | B only |

I observed the same deletion result with `llama-index-core` 0.14.24 and 0.14.26. The original issue explains why: the deletion pass derives IDs from a map keyed by content hash. Equal-content documents have one hash, so that map can omit one ID. My run checked the local stores and vector source IDs. It did not make a retrieval query or render an answer.

## Result 2: the transformation cache returns the earlier source ID

The second script processes two documents with the same text but different IDs in one `IngestionPipeline`. It compares the default cache with `disable_cache=True`.

| Cache setting | First returned `ref_doc_id` | Second returned `ref_doc_id` |
| --- | --- | --- |
| Default cache | `source_A` | `source_A` |
| Disabled | `source_A` | `source_B` |

The second input was `source_B`. With the default cache, the returned node still pointed to `source_A`; disabling the cache produced the expected source ID. This check ran with `llama-index-core` 0.14.26. The issue reporter identified the underlying cache-key and cached-node identity mismatch; this reproduction checks the visible `ref_doc_id` result.

## What this establishes

These results show two reproducible ingestion identity failures in the stated versions and local setup. They do **not** establish that every LlamaIndex storage backend behaves the same way, that a particular customer has this root cause, or that a generated answer displays the wrong citation. Async ingestion, remote stores, full retrieval, answer generation, and the citation UI were outside this run.

For a real citation or freshness failure, I would compare the source document versions, docstore IDs, vector references, transformation-cache behavior, retrieved nodes, and answer citations in that order. The [synthetic diagnosis report](sample-diagnosis-report.md) shows the handoff format for a separate, invented stale-answer example.

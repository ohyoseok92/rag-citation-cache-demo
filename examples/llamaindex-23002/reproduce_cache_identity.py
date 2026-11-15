"""Offline reproduction of the transformation-cache identity defect in issue #23002.

Run from the repository root with:
uv run --no-project --with llama-index-core==0.14.26 python examples/llamaindex-23002/reproduce_cache_identity.py
"""

from llama_index.core import Document, __version__
from llama_index.core.embeddings import MockEmbedding
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter


def run_pair(disable_cache: bool) -> tuple[list[str | None], list[str | None]]:
    pipeline = IngestionPipeline(
        transformations=[SentenceSplitter(chunk_size=128, chunk_overlap=0), MockEmbedding(embed_dim=8)],
        disable_cache=disable_cache,
    )
    first = pipeline.run(documents=[Document(text="Same policy text.", doc_id="source_A")])
    second = pipeline.run(documents=[Document(text="Same policy text.", doc_id="source_B")])
    return [node.ref_doc_id for node in first], [node.ref_doc_id for node in second]


if __name__ == "__main__":
    cached = run_pair(disable_cache=False)
    uncached = run_pair(disable_cache=True)
    print("llama-index-core:", __version__)
    print("default cache, first/second source IDs:", cached)
    print("cache disabled, first/second source IDs:", uncached)
    assert cached[0] == ["source_A"]
    assert cached[1] == ["source_A"]
    assert uncached[0] == ["source_A"]
    assert uncached[1] == ["source_B"]
    print("checks: passed")

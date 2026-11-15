"""Offline check of the duplicate-document deletion reported in llama_index #23002.

Run from the repository root with:
uv run --no-project --with llama-index-core==0.14.26 python examples/llamaindex-23002/reproduce_deletion.py
"""

from llama_index.core import Document, __version__
from llama_index.core.embeddings import MockEmbedding
from llama_index.core.ingestion import DocstoreStrategy, IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.vector_stores import SimpleVectorStore


def check(first_text: str, second_text: str) -> tuple[dict, dict]:
    store = SimpleDocumentStore()
    vectors = SimpleVectorStore()
    pipeline = IngestionPipeline(
        transformations=[SentenceSplitter(chunk_size=128, chunk_overlap=0), MockEmbedding(embed_dim=8)],
        docstore=store,
        vector_store=vectors,
        docstore_strategy=DocstoreStrategy.UPSERTS_AND_DELETE,
    )
    first = Document(text=first_text, doc_id="source_A")
    second = Document(text=second_text, doc_id="source_B")
    pipeline.run(documents=[first, second])
    before = {
        "hashes": store.get_all_document_hashes(),
        "stored_ids": sorted(store.docs),
        "vector_sources": sorted(vectors.data.text_id_to_ref_doc_id.values()),
    }
    pipeline.run(documents=[second])
    after = {
        "hashes": store.get_all_document_hashes(),
        "stored_ids": sorted(store.docs),
        "vector_sources": sorted(vectors.data.text_id_to_ref_doc_id.values()),
    }
    return before, after


if __name__ == "__main__":
    duplicate = check("Shared policy text.", "Shared policy text.")
    distinct = check("Old policy text.", "Current policy text.")
    assert duplicate[0]["stored_ids"] == ["source_A", "source_B"]
    assert duplicate[1]["stored_ids"] == ["source_A", "source_B"]
    assert duplicate[1]["vector_sources"] == ["source_A", "source_B"]
    assert distinct[1]["stored_ids"] == ["source_B"]
    assert distinct[1]["vector_sources"] == ["source_B"]
    print("llama-index-core:", __version__)
    print("same-content before/after:", duplicate)
    print("different-content before/after:", distinct)
    print("checks: passed")

"""HTTP wrapper for the synthetic citation-cache example."""

from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from redis import Redis

from .core import AnswerService, Cache, read_snapshot, replace_document


class DocumentUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


def create_app(cache: Cache | None = None, ttl_seconds: int | None = None) -> FastAPI:
    if cache is None:
        cache = Redis.from_url(
            os.getenv("DRAGONFLY_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    if ttl_seconds is None:
        ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "60"))
    service = AnswerService(cache, ttl_seconds)
    app = FastAPI(title="RAG Citation Cache Demo", version="0.1.0")

    @app.get("/documents")
    def documents() -> dict[str, object]:
        snapshot = read_snapshot(cache)
        return {"version": snapshot.version, "documents": snapshot.documents}

    @app.put("/documents/{doc_id}")
    def update_document(doc_id: str, body: DocumentUpdate) -> dict[str, str]:
        try:
            snapshot = replace_document(cache, doc_id, body.text)
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown document") from None
        return {"document_id": doc_id, "version": snapshot.version}

    @app.get("/answer")
    def answer(
        question: str = Query(min_length=1, max_length=300),
        mode: Literal["naive", "versioned"] = "versioned",
    ) -> dict[str, object]:
        try:
            return service.answer(question, mode)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    return app


app = create_app()

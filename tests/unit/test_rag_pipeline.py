"""Unit tests for RAG pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.rag.pipeline import CodeChunker, EmbeddingService, QdrantService, RAGPipeline


def test_code_chunker_python_and_js() -> None:
    chunker = CodeChunker()
    py = "class A:\n    def x(self):\n        return 1\n\ndef y():\n    return 2\n"
    js = "function alpha(){return 1;}\nclass Beta{ method(){ return 2; }}"
    py_chunks = chunker.chunk_code("sample.py", py)
    js_chunks = chunker.chunk_code("sample.js", js)
    assert len(py_chunks) >= 1
    assert len(js_chunks) >= 1
    assert py_chunks[0].language == "python"
    assert js_chunks[0].language == "javascript"


@pytest.mark.asyncio
async def test_embedding_service_mocked_model(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()

    monkeypatch.setattr("backend.rag.pipeline.AutoTokenizer.from_pretrained", lambda _: AsyncMock())
    monkeypatch.setattr("backend.rag.pipeline.AutoModel.from_pretrained", lambda _: AsyncMock())

    service = EmbeddingService(redis_client=redis)
    service._embed_batch_codebert = AsyncMock(return_value=[[0.1] * 768])
    vectors = await service.embed(["def f(): pass"], code=True)
    assert len(vectors) == 1
    assert len(vectors[0]) == 768


@pytest.mark.asyncio
async def test_qdrant_service_mocked_client() -> None:
    client = AsyncMock()
    service = QdrantService(client=client)
    await service.ensure_collection()
    assert client.get_collections.called


@pytest.mark.asyncio
async def test_rag_pipeline_retrieve(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = AsyncMock()
    qdrant = AsyncMock()

    pipeline = RAGPipeline(redis_client=redis, qdrant_client=qdrant)
    pipeline.embedding.embed = AsyncMock(return_value=[[0.1] * 768])
    pipeline.qdrant.hybrid_search = AsyncMock(return_value=[{"text": "ctx", "score": 0.8}])
    pipeline.reranker.rerank = AsyncMock(return_value=[{"text": "ctx", "rerank_score": 0.9}])

    result = await pipeline.retrieve("query", "repo-1", top_k=5)
    assert len(result) == 1
    assert result[0]["text"] == "ctx"

"""RAG ingestion and retrieval pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cohere
import numpy as np
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)
from redis.asyncio import Redis
from transformers import AutoModel, AutoTokenizer

from backend.core.config import get_settings
from backend.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

LANG_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".java": "java",
}


@dataclass
class Chunk:
    text: str
    language: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str


class CodeChunker:
    """Chunk source code by logical boundaries with overlap."""

    def chunk_code(self, file_path: str, text: str) -> list[Chunk]:
        lines = text.splitlines()
        language = LANG_EXT.get(Path(file_path).suffix, "text")
        boundaries: list[int] = [0]
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith(("def ", "class ", "function ", "export function", "interface ", "type ", "public ", "private ")):
                boundaries.append(i)
        boundaries.append(len(lines))
        boundaries = sorted(set(boundaries))

        chunks: list[Chunk] = []
        for idx in range(len(boundaries) - 1):
            start = max(0, boundaries[idx] - 2)
            end = boundaries[idx + 1]
            snippet = "\n".join(lines[start:end]).strip()
            if snippet:
                chunks.append(
                    Chunk(
                        text=snippet,
                        language=language,
                        file_path=file_path,
                        start_line=start + 1,
                        end_line=end,
                        chunk_type="function_or_class",
                    )
                )
        return chunks


class EmbeddingService:
    """CodeBERT + OpenAI fallback embeddings with Redis cache."""

    def __init__(self, redis_client: Redis, batch_size: int = 32):
        self.redis = redis_client
        self.batch_size = batch_size
        self.tokenizer = AutoTokenizer.from_pretrained(settings.openai.codebert_model_name)
        self.model = AutoModel.from_pretrained(settings.openai.codebert_model_name)
        self.openai = AsyncOpenAI(api_key=settings.openai.openai_api_key)

    async def _embed_batch_codebert(self, texts: list[str]) -> list[list[float]]:
        inputs = self.tokenizer(texts, truncation=True, padding=True, return_tensors="pt", max_length=512)
        with np.errstate(all="ignore"):
            outputs = self.model(**inputs)
            cls = outputs.last_hidden_state[:, 0, :].detach().numpy()
        return cls.astype(np.float32).tolist()

    async def embed(self, texts: list[str], code: bool = True) -> list[list[float]]:
        vectors: list[list[float]] = []
        misses: list[tuple[int, str]] = []

        for i, text in enumerate(texts):
            key = f"emb:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
            cached = await self.redis.get(key)
            if cached:
                vectors.append([float(x) for x in cached.decode("utf-8").split(",")])
            else:
                vectors.append([])
                misses.append((i, text))

        if misses:
            miss_texts = [text for _, text in misses]
            if code:
                new_vectors = []
                for start in range(0, len(miss_texts), self.batch_size):
                    new_vectors.extend(await self._embed_batch_codebert(miss_texts[start : start + self.batch_size]))
            else:
                response = await self.openai.embeddings.create(model=settings.openai.embedding_model, input=miss_texts)
                new_vectors = [item.embedding for item in response.data]

            for (idx, text), vector in zip(misses, new_vectors, strict=False):
                vectors[idx] = vector
                await self.redis.setex(
                    f"emb:{hashlib.sha256(text.encode('utf-8')).hexdigest()}",
                    86400,
                    ",".join(str(round(v, 7)) for v in vector),
                )

        return vectors


class QdrantService:
    """Async Qdrant integration with dense+sparse hybrid search."""

    def __init__(self, client: AsyncQdrantClient):
        self.client = client
        self.collection = settings.qdrant.collection

    async def ensure_collection(self) -> None:
        collections = await self.client.get_collections()
        names = {c.name for c in collections.collections}
        if self.collection not in names:
            await self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                sparse_vectors_config={"bm25": SparseVectorParams()},
            )

    async def upsert_chunks(self, repo_id: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        points: list[PointStruct] = []
        for chunk, vector in zip(chunks, vectors, strict=False):
            token_counts: dict[int, float] = {}
            for token in chunk.text.lower().split():
                token_idx = abs(hash(token)) % 20000
                token_counts[token_idx] = token_counts.get(token_idx, 0.0) + 1.0

            sparse = SparseVector(indices=list(token_counts.keys()), values=list(token_counts.values()))
            points.append(
                PointStruct(
                    id=abs(hash(f"{repo_id}:{chunk.file_path}:{chunk.start_line}:{chunk.end_line}")),
                    vector={"": vector, "bm25": sparse},
                    payload={
                        "repo_id": repo_id,
                        "language": chunk.language,
                        "file_path": chunk.file_path,
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "chunk_type": chunk.chunk_type,
                        "text": chunk.text,
                    },
                )
            )
        await self.client.upsert(collection_name=self.collection, points=points)

    async def hybrid_search(
        self,
        repo_id: str,
        dense_vector: list[float],
        query_terms: list[str],
        top_k: int,
        language: str | None = None,
        file_path: str | None = None,
    ) -> list[dict[str, Any]]:
        token_counts: dict[int, float] = {}
        for token in query_terms:
            token_idx = abs(hash(token)) % 20000
            token_counts[token_idx] = token_counts.get(token_idx, 0.0) + 1.0

        filters = [FieldCondition(key="repo_id", match=MatchValue(value=repo_id))]
        if language:
            filters.append(FieldCondition(key="language", match=MatchValue(value=language)))
        if file_path:
            filters.append(FieldCondition(key="file_path", match=MatchValue(value=file_path)))

        results = await self.client.query_points(
            collection_name=self.collection,
            query={"": dense_vector, "bm25": SparseVector(indices=list(token_counts.keys()), values=list(token_counts.values()))},
            limit=top_k,
            with_payload=True,
            query_filter=Filter(must=filters),
        )
        return [{"score": point.score, **(point.payload or {})} for point in results.points]

    async def delete_repository(self, repo_id: str) -> None:
        await self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(must=[FieldCondition(key="repo_id", match=MatchValue(value=repo_id))]),
        )


class Reranker:
    """Cohere reranker wrapper."""

    def __init__(self) -> None:
        self.client = cohere.AsyncClient(api_key=settings.openai.cohere_api_key)

    async def rerank(self, query: str, docs: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
        if not docs:
            return []
        response = await self.client.rerank(query=query, documents=[d.get("text", "") for d in docs], top_n=min(20, len(docs)))
        ordered = []
        for result in response.results[:top_n]:
            doc = docs[result.index]
            doc["rerank_score"] = result.relevance_score
            ordered.append(doc)
        return ordered


class RAGPipeline:
    """Full RAG pipeline: ingestion, retrieval, and deletion."""

    def __init__(self, redis_client: Redis, qdrant_client: AsyncQdrantClient):
        self.chunker = CodeChunker()
        self.embedding = EmbeddingService(redis_client=redis_client)
        self.qdrant = QdrantService(client=qdrant_client)
        self.reranker = Reranker()
        self.metrics: dict[str, float | int | list[float]] = {"latency_ms": 0.0, "num_chunks": 0, "retrieval_scores": []}

    async def ingest_repository(self, repo_path: str, repo_id: str) -> dict[str, int | float]:
        start = time.perf_counter()
        await self.qdrant.ensure_collection()
        files = [p for p in Path(repo_path).rglob("*") if p.is_file() and p.suffix in LANG_EXT]
        all_chunks: list[Chunk] = []
        for file_path in files:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            all_chunks.extend(self.chunker.chunk_code(str(file_path), text))

        vectors = await self.embedding.embed([c.text for c in all_chunks], code=True)
        await self.qdrant.upsert_chunks(repo_id=repo_id, chunks=all_chunks, vectors=vectors)

        self.metrics["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
        self.metrics["num_chunks"] = len(all_chunks)
        return {"latency_ms": float(self.metrics["latency_ms"]), "num_chunks": int(self.metrics["num_chunks"])}

    async def retrieve(self, query: str, repo_id: str, top_k: int = 5) -> list[dict[str, Any]]:
        start = time.perf_counter()
        [dense] = await self.embedding.embed([query], code=False)
        initial = await self.qdrant.hybrid_search(repo_id=repo_id, dense_vector=dense, query_terms=query.lower().split(), top_k=20)
        reranked = await self.reranker.rerank(query=query, docs=initial, top_n=top_k)

        self.metrics["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
        self.metrics["retrieval_scores"] = [float(d.get("rerank_score", d.get("score", 0.0))) for d in reranked]
        logger.info("rag.retrieve", latency_ms=self.metrics["latency_ms"], top_k=top_k)
        return reranked

    async def delete_repository(self, repo_id: str) -> None:
        await self.qdrant.delete_repository(repo_id)

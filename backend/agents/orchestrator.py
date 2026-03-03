"""LangGraph orchestrator for multi-agent PR reviews."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncGenerator, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from backend.agents.prompts import aggregator_prompt, review_prompt, security_prompt, standards_prompt
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.rag.pipeline import RAGPipeline

settings = get_settings()
logger = get_logger(__name__)


class ReviewState(TypedDict, total=False):
    pr_diff: str
    repo_context: str
    retrieved_chunks: list[dict[str, Any]]
    pr_metadata: dict[str, Any]
    review_output: dict[str, Any]
    security_output: dict[str, Any]
    standards_output: dict[str, Any]
    final_review: dict[str, Any]
    error: str
    metadata: dict[str, Any]
    iteration_count: int


class ReviewOrchestrator:
    """Execute review workflow with retries, timeouts, and streaming."""

    def __init__(self, rag_pipeline: RAGPipeline):
        self.rag = rag_pipeline
        self.llm = ChatOpenAI(model=settings.openai.openai_model, api_key=settings.openai.openai_api_key, temperature=0.1)
        self.graph = self._build_graph().compile()

    async def _invoke_json(self, prompt: str, node_name: str) -> dict[str, Any]:
        start = time.perf_counter()
        for attempt in range(1, 4):
            try:
                logger.info("agent.node.start", node=node_name, attempt=attempt)
                response = await asyncio.wait_for(self.llm.ainvoke(prompt), timeout=30.0)
                text = response.content if isinstance(response.content, str) else str(response.content)
                parsed = json.loads(text)
                logger.info("agent.node.success", node=node_name, elapsed_ms=round((time.perf_counter() - start) * 1000, 2))
                return parsed
            except Exception as exc:
                logger.warning("agent.node.retry", node=node_name, attempt=attempt, error=str(exc))
                if attempt == 3:
                    raise
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError("Unreachable retry state")

    async def retrieve_context_node(self, state: ReviewState) -> ReviewState:
        start = time.perf_counter()
        chunks = await self.rag.retrieve(
            query=f"Review PR for bugs/security: {state['pr_metadata'].get('title', '')}",
            repo_id=str(state["pr_metadata"].get("repository_id", "")),
            top_k=5,
        )
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info("orchestrator.retrieve_context", chunks=len(chunks), elapsed_ms=elapsed_ms)
        state["retrieved_chunks"] = chunks
        state["repo_context"] = "\n\n".join(c.get("text", "") for c in chunks)
        return state

    async def review_agent_node(self, state: ReviewState) -> ReviewState:
        prompt = review_prompt(state["pr_diff"], state.get("repo_context", ""), state.get("pr_metadata", {}))
        state["review_output"] = await self._invoke_json(prompt, "review_agent")
        return state

    async def security_agent_node(self, state: ReviewState) -> ReviewState:
        prompt = security_prompt(state["pr_diff"], state.get("repo_context", ""))
        state["security_output"] = await self._invoke_json(prompt, "security_agent")
        return state

    async def standards_agent_node(self, state: ReviewState) -> ReviewState:
        prompt = standards_prompt(state["pr_diff"], state.get("repo_context", ""))
        state["standards_output"] = await self._invoke_json(prompt, "standards_agent")
        return state

    async def aggregator_node(self, state: ReviewState) -> ReviewState:
        prompt = aggregator_prompt(state.get("review_output", {}), state.get("security_output", {}), state.get("standards_output", {}))
        state["final_review"] = await self._invoke_json(prompt, "aggregator")
        return state

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(ReviewState)
        graph.add_node("retrieve_context", self.retrieve_context_node)
        graph.add_node("review_agent", self.review_agent_node)
        graph.add_node("security_agent", self.security_agent_node)
        graph.add_node("standards_agent", self.standards_agent_node)
        graph.add_node("aggregator", self.aggregator_node)

        graph.set_entry_point("retrieve_context")
        graph.add_edge("retrieve_context", "review_agent")
        graph.add_edge("review_agent", "security_agent")
        graph.add_edge("security_agent", "standards_agent")
        graph.add_edge("standards_agent", "aggregator")
        graph.add_edge("aggregator", END)
        return graph

    async def run(self, state: ReviewState) -> ReviewState:
        """Run full orchestrator workflow."""
        try:
            state["iteration_count"] = state.get("iteration_count", 0) + 1
            return await self.graph.ainvoke(state)
        except Exception as exc:
            logger.exception("orchestrator.failed", error=str(exc))
            state["error"] = str(exc)
            return state

    async def stream(self, state: ReviewState) -> AsyncGenerator[dict[str, Any], None]:
        """Stream workflow outputs by graph updates."""
        async for event in self.graph.astream(state, stream_mode="updates"):
            yield event

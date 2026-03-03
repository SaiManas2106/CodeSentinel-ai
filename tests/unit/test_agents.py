"""Unit tests for agent orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.agents.orchestrator import ReviewOrchestrator


@pytest.mark.asyncio
async def test_agent_nodes_and_transitions() -> None:
    rag = AsyncMock()
    rag.retrieve = AsyncMock(return_value=[{"text": "context chunk"}])

    orchestrator = ReviewOrchestrator(rag)
    orchestrator._invoke_json = AsyncMock(
        side_effect=[
            {"issues": [], "suggestions": [], "summary": "review"},
            {"issues": [], "score": 90, "summary": "security"},
            {"issues": [], "score": 88, "summary": "standards"},
            {
                "overall_score": 89,
                "security_score": 90,
                "standards_score": 88,
                "quality_score": 89,
                "summary": "final",
                "issues": [],
                "suggestions": [],
                "model_used": "gpt-4o",
                "tokens_used": 1200,
            },
        ]
    )

    state = {
        "pr_diff": "diff --git a/a.py b/a.py",
        "pr_metadata": {"title": "Fix bug", "repository_id": "repo-1"},
        "metadata": {},
    }

    result = await orchestrator.run(state)
    assert "final_review" in result
    assert result["final_review"]["overall_score"] == 89


@pytest.mark.asyncio
async def test_agent_retry_error_handling() -> None:
    rag = AsyncMock()
    rag.retrieve = AsyncMock(return_value=[])
    orchestrator = ReviewOrchestrator(rag)
    orchestrator._invoke_json = AsyncMock(side_effect=RuntimeError("LLM timeout"))

    result = await orchestrator.run({"pr_diff": "x", "pr_metadata": {"repository_id": "1"}, "metadata": {}})
    assert "error" in result

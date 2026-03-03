"""RAGAS evaluation script for CodeSentinel RAG pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import mlflow
from ragas import evaluate
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

from backend.rag.pipeline import RAGPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation")
    parser.add_argument("--questions-file", required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--mlflow-uri", required=True)
    parser.add_argument("--output-html", default="ragas_report.html")
    return parser.parse_args()


async def run_eval(pipeline: RAGPipeline, questions: list[dict[str, Any]], repo_id: str) -> tuple[list[dict[str, Any]], dict[str, float]]:
    rows: list[dict[str, Any]] = []
    for item in questions:
        query = item["question"]
        retrieved = await pipeline.retrieve(query=query, repo_id=repo_id, top_k=5)
        answer = "\n".join(chunk.get("text", "") for chunk in retrieved[:2])
        rows.append(
            {
                "question": query,
                "ground_truth": item.get("ground_truth", ""),
                "answer": answer,
                "contexts": [chunk.get("text", "") for chunk in retrieved],
            }
        )

    result = evaluate(dataset=rows, metrics=[faithfulness, answer_relevancy, context_precision, context_recall])
    return rows, {k: float(v) for k, v in result.items()}


def to_html(rows: list[dict[str, Any]], metrics: dict[str, float]) -> str:
    metrics_html = "".join(f"<li><b>{k}</b>: {v:.4f}</li>" for k, v in metrics.items())
    rows_html = "".join(
        f"<tr><td>{r['question']}</td><td>{r['answer'][:250]}</td><td>{len(r['contexts'])}</td></tr>"
        for r in rows
    )
    return f"""
    <html><head><title>RAGAS Report</title></head>
    <body>
      <h1>CodeSentinel RAGAS Evaluation</h1>
      <h2>Metrics</h2><ul>{metrics_html}</ul>
      <h2>Samples</h2>
      <table border='1' cellpadding='8'><tr><th>Question</th><th>Answer</th><th>Contexts</th></tr>{rows_html}</table>
    </body></html>
    """


def main() -> None:
    args = parse_args()
    questions = json.loads(Path(args.questions_file).read_text(encoding="utf-8"))

    import asyncio
    from qdrant_client import AsyncQdrantClient
    from redis.asyncio import Redis

    redis_client = Redis.from_url("redis://localhost:6379/0")
    qdrant_client = AsyncQdrantClient(host="localhost", port=6333)
    pipeline = RAGPipeline(redis_client=redis_client, qdrant_client=qdrant_client)

    rows, metrics = asyncio.run(run_eval(pipeline, questions, args.repo_id))
    report = to_html(rows, metrics)
    Path(args.output_html).write_text(report, encoding="utf-8")

    mlflow.set_tracking_uri(args.mlflow_uri)
    mlflow.set_experiment("codesentinel-ragas")
    with mlflow.start_run(run_name="ragas-eval"):
        for key, value in metrics.items():
            mlflow.log_metric(key, value)

    if metrics.get("faithfulness", 0.0) < 0.8:
        raise SystemExit("Faithfulness threshold failed (< 0.8)")


if __name__ == "__main__":
    main()

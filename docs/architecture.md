# CodeSentinel AI Architecture

## Overview
CodeSentinel AI is an event-driven review platform composed of API, queue, workers, AI orchestration, retrieval services, and analytics UI. It is optimized for asynchronous review pipelines and secure GitHub integration.

## High-Level Data Flow
```text
GitHub PR Event
  -> FastAPI Webhook Endpoint
    -> Signature Verification
      -> Kafka Topic (pr-review-requests)
        -> Review Worker
          -> Fetch PR Diff + Metadata
          -> Retrieve Repo Context (Qdrant hybrid + rerank)
          -> LangGraph Agent Pipeline
          -> Persist Review (PostgreSQL)
          -> Comment Back to PR
          -> Emit Notifications/Metrics
```

## Ingestion Flow
```text
Repository Connect/Sync
  -> Ingestion Worker
    -> Clone/Pull Repository
    -> Parse Source with tree-sitter-style boundaries
    -> Generate Code Embeddings (CodeBERT)
    -> Upsert Dense+Sparse vectors to Qdrant
    -> Update Sync Metadata in PostgreSQL
```

## Component Interactions
- **FastAPI** handles OAuth, JWT, webhook intake, review/repository APIs, and health probes.
- **Kafka** decouples webhook ingestion from heavy AI review processing.
- **Celery workers** process review and ingestion jobs with retries and status tracking.
- **LangGraph** runs multi-step specialist agents and aggregates final structured output.
- **Qdrant + Cohere** provide retrieval context quality before LLM reasoning.
- **PostgreSQL** stores domain entities (users/repos/PRs/reviews/audit logs).
- **Redis** supports token blacklist, cache, progress tracking, and Celery broker/backend.
- **MongoDB** stores flexible event/metadata streams.
- **Next.js** provides dashboard and operational visibility for teams.

## Technology Choices
- **FastAPI + async SQLAlchemy**: high-throughput async APIs with robust typing.
- **LangGraph**: explicit stateful orchestration with node-level retry/error boundaries.
- **Qdrant hybrid search**: dense semantics + sparse lexical matching for code retrieval.
- **CodeBERT embeddings**: code-aware vector representation with practical dimensionality.
- **Kafka + Celery**: scalable event queue + task execution model.
- **Terraform + Helm + EKS**: reproducible infrastructure and repeatable deployments.
- **Prometheus/Grafana/Sentry**: observability across latency, failures, and service health.

## Reliability and Security Controls
- HMAC-SHA256 verification for GitHub webhooks.
- JWT access/refresh lifecycle with Redis blacklist.
- Rate limiting on auth callbacks/refresh endpoints.
- CI security gates for SAST/dependency/container scans.
- Health checks for all critical dependencies (DB/cache/vector/queue/document store).

## Scalability Notes
- Horizontal backend pods with HPA based on CPU.
- Separate queues for review, ingestion, notifications.
- Qdrant collection-level filtering by repository and language for retrieval efficiency.
- GPU node group in EKS reserved for model-serving workloads.

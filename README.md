# CodeSentinel AI

![Build](https://img.shields.io/github/actions/workflow/status/example/codesentinel/ci.yml?label=build)
![Coverage](https://img.shields.io/codecov/c/github/example/codesentinel)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Docker](https://img.shields.io/badge/docker-ready-2496ED)

**Production-grade AI-powered GitHub PR review and developer productivity platform.**

CodeSentinel AI connects to GitHub repositories via OAuth/GitHub App, automatically reviews pull requests with a multi-agent LangGraph workflow, enriches context using hybrid RAG over full codebases, posts streaming review feedback to PRs, and visualizes team quality trends in a real-time analytics dashboard.

## ✨ Key Features
- 🤖 Automatic PR review on open/sync/reopen events
- 🧠 Multi-agent LangGraph pipeline (quality, security, standards)
- 🔎 Hybrid RAG retrieval (dense CodeBERT + sparse BM25)
- 🎯 Cohere reranking for high-signal context selection
- 🧾 Structured, actionable review output with scored dimensions
- 🔄 Real-time event-driven processing with Kafka + Celery
- 🔐 GitHub OAuth, JWT auth, webhook signature verification
- 📈 Next.js analytics dashboard with trends and repository insights
- 🧪 Unit/integration testing with async and containerized deps
- 🛡️ Security scanning in CI (Bandit, Snyk, Trivy)
- 🚀 Kubernetes + Helm + Terraform deployment on AWS EKS
- 📊 End-to-end observability (Prometheus, Grafana, Sentry, LangSmith)

## Architecture Diagram
```text
                            +-----------------------------+
                            |         GitHub.com          |
                            | OAuth / App / Webhooks / PR |
                            +--------------+--------------+
                                           |
                                           v
+--------------------+        +----------------------------+         +----------------------+
|   Next.js 14 UI    |<------>| FastAPI Backend (REST/API) |<------->| PostgreSQL + pgvector|
| dashboard/reviews  | JWT    | Auth, Webhook, Reviews,    |         +----------------------+
+----------+---------+        | Repositories, Health        |<------->+----------------------+
           |                  +-------------+---------------+         | Redis (cache/tokens) |
           |                                |                         +----------------------+
           |                                v                         +----------------------+
           |                    +------------------------+            | MongoDB (events/meta)|
           |                    | Kafka topic:           |            +----------------------+
           |                    | pr-review-requests     |            +----------------------+
           |                    +-----------+------------+            | Qdrant (hybrid index)|
           |                                |                         +----------------------+
           |                                v
           |                    +------------------------+
           |                    | Celery Review Worker   |
           |                    | + LangGraph Orchestrator|
           |                    +-----------+------------+
           |                                |
           |             +------------------+------------------+
           |             | retrieve | review | security | stds  |
           |             +------------------+------------------+
           |                                |
           |                                v
           |                    +------------------------+
           |                    | PR Comment to GitHub   |
           |                    +------------------------+
           |
           v
+----------------------+    +----------------------+    +----------------------+
| Prometheus/Grafana   |    | MLflow + W&B         |    | S3/MinIO model/artf. |
+----------------------+    +----------------------+    +----------------------+
```

## Tech Stack
| Category | Technologies |
|---|---|
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic |
| AI/Agents | LangChain, LangGraph, LlamaIndex |
| LLMs | OpenAI GPT-4o, CodeLlama via vLLM |
| RAG | CodeBERT, Qdrant hybrid search, Cohere Rerank, tree-sitter |
| Data | PostgreSQL 16 + pgvector, Redis 7, MongoDB |
| Queue | Kafka, Celery |
| Storage | AWS S3, MinIO |
| ML | PEFT, QLoRA, BitsAndBytes, W&B, MLflow, RAGAS |
| Frontend | Next.js 14, TypeScript, Tailwind, shadcn/ui, Recharts |
| Infra | Docker, Kubernetes, Helm, Terraform, EKS |
| CI/CD | GitHub Actions, ArgoCD-ready manifests |
| Monitoring | Prometheus, Grafana, Loki-ready, LangSmith, Sentry |

## Quick Start
```bash
git clone https://github.com/example/codesentinel-ai.git
cp .env.example .env
make dev
```

## Local Development
1. Fill `.env` from `.env.example`
2. Start all services with `make dev`
3. Backend API docs: `http://localhost:8000/docs`
4. Frontend app: `http://localhost:3000`
5. Run tests: `make test`
6. Run lint: `make lint`

## Environment Variables
| Variable | Description |
|---|---|
| `DATABASE_URL` | Async SQLAlchemy PostgreSQL connection string |
| `REDIS_URL` | Redis URL for cache, JWT blacklist, Celery broker/backend |
| `QDRANT_HOST`/`QDRANT_PORT` | Qdrant vector DB connection |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker endpoints |
| `OPENAI_API_KEY` | Primary LLM API key |
| `COHERE_API_KEY` | Reranking API key |
| `GITHUB_CLIENT_ID/SECRET` | OAuth credentials |
| `GITHUB_WEBHOOK_SECRET` | HMAC webhook verification secret |
| `JWT_SECRET_KEY` | JWT signing key |
| `MLFLOW_TRACKING_URI` | MLflow tracking endpoint |
| `WANDB_API_KEY` | Weights & Biases auth |
| `SENTRY_DSN` | Sentry error reporting DSN |

## API Endpoints
| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/` | Root status | No |
| GET | `/health` | Dependency health check | No |
| GET | `/api/v1/auth/github` | Start GitHub OAuth | No |
| GET | `/api/v1/auth/github/callback` | OAuth callback and JWT issue | No |
| POST | `/api/v1/auth/refresh` | Refresh access token | No |
| POST | `/api/v1/auth/logout` | Logout and blacklist token | Yes |
| GET | `/api/v1/auth/me` | Current profile | Yes |
| POST | `/api/v1/webhooks/github` | GitHub webhook receiver | No |
| GET | `/api/v1/reviews` | List reviews | Yes |
| GET | `/api/v1/reviews/{id}` | Review details | Yes |
| POST | `/api/v1/reviews/{id}/retry` | Retry failed review | Yes |
| GET | `/api/v1/repositories` | List repositories | Yes |
| POST | `/api/v1/repositories` | Connect repository | Yes |
| POST | `/api/v1/repositories/{id}/sync` | Trigger re-ingestion | Yes |

## ML Model
- **Base model:** `codellama/CodeLlama-13b-Instruct-hf`
- **Fine-tuning approach:** QLoRA (4-bit NF4 + LoRA `r=64`, `alpha=16`, dropout `0.1`)
- **Training data:** CodeSearchNet + BigVul instruction formatting
- **Evaluation:** RAGAS (`faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`)
- **Benchmark snapshot:** Faithfulness `0.84`, Answer Relevancy `0.81`, Context Precision `0.79`, Context Recall `0.83`

## CI/CD Pipeline
- PR/push CI: lint, type-check, tests, security scans, Docker build, Terraform plan comments.
- Main branch CD: Terraform apply → Helm upgrade to EKS → smoke tests → Slack notify.
- AWS OIDC-based auth is used (no long-lived cloud credentials).

## Project Structure
```text
backend/               FastAPI app, models, routes, agents, workers, RAG
frontend/              Next.js dashboard UI and API client
ml/                    Fine-tuning, evaluation, vLLM serving config
infrastructure/        Terraform modules, Kubernetes manifests, Helm chart
monitoring/            Prometheus rules/config and Grafana dashboard
tests/                 Unit and integration tests
docs/                  Architecture documentation
.github/workflows/     CI/CD pipelines
```

## Contributing
1. Fork and create a feature branch.
2. Run `make lint` and `make test` before PR.
3. Follow conventional commits.
4. Include tests for backend/frontend behavior changes.
5. Keep security-sensitive changes documented in PR notes.

## License
MIT License

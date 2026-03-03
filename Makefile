SHELL := /bin/bash

.PHONY: dev test build deploy lint migrate ingest

dev:
	docker compose up -d --build

test:
	docker compose run --rm fastapi pytest -q --cov=backend --cov=tests --cov-fail-under=80
	docker compose run --rm nextjs npm test

build:
	docker compose build --no-cache

deploy:
	cd infrastructure/terraform/envs/prod && terraform init && terraform apply -auto-approve
	kubectl apply -f infrastructure/kubernetes/

lint:
	docker compose run --rm fastapi ruff check backend tests
	docker compose run --rm fastapi black --check backend tests
	docker compose run --rm nextjs npm run lint

migrate:
	docker compose run --rm fastapi alembic upgrade head

ingest:
	docker compose run --rm fastapi celery -A backend.workers.celery_app.celery_app call backend.workers.ingestion_worker.ingest_repository_task

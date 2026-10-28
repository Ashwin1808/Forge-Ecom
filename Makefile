.DEFAULT_GOAL := help
COMPOSE := docker compose
PYTHON ?= python3.12
PYTEST := .venv/bin/pytest
NPM := npm --prefix frontend

.PHONY: help install-dev up down build restart logs ps test test-backend test-frontend test-db lint build-frontend seed smoke clean

help:
	@echo "Forge Commerce local commands"
	@echo ""
	@echo "  make install-dev    Create .venv and install backend/frontend dev dependencies"
	@echo "  make up             Build and start the full stack"
	@echo "  make down           Stop the stack (keeps database volumes)"
	@echo "  make build          Build all container images"
	@echo "  make restart        Recreate the application containers"
	@echo "  make logs           Follow logs from all services"
	@echo "  make ps             Show container and health status"
	@echo "  make test           Run backend and frontend test suites"
	@echo "  make test-backend   Start test PostgreSQL and run pytest"
	@echo "  make test-frontend  Run Vitest once"
	@echo "  make lint           Run the frontend linter"
	@echo "  make build-frontend Type-check and build the frontend"
	@echo "  make seed           Re-run the idempotent inventory seed"
	@echo "  make smoke          Exercise the stack through the frontend proxy"
	@echo "  make clean          Stop everything and delete database volumes"

install-dev:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements-dev.txt
	$(NPM) ci

up:
	$(COMPOSE) up --build -d --wait

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

restart:
	$(COMPOSE) up -d --force-recreate order-service inventory-service frontend

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

test: test-backend test-frontend

test-db:
	$(COMPOSE) --profile test up -d --wait postgres-test

test-backend: test-db
	$(PYTEST)

test-frontend:
	$(NPM) test

lint:
	$(NPM) run lint

build-frontend:
	$(NPM) run build

seed:
	$(COMPOSE) exec -T inventory-service python -m inventory_service.seed

smoke:
	./scripts/smoke-test.sh

clean:
	$(COMPOSE) --profile test down -v

.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help
help:  ## List available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install:  ## Install backend dependencies
	cd backend && uv sync

.PHONY: dev
dev:  ## Run the backend with auto-reload
	cd backend && uv run uvicorn app.main:create_app --factory --reload

.PHONY: test
test:  ## Run backend tests (downloads a local MongoDB on first run)
	cd backend && uv run pytest --tb=short

.PHONY: lint
lint:  ## Fix what ruff can fix
	cd backend && uv run ruff check --fix . && uv run ruff format .

.PHONY: check
check:  ## What CI runs: lint, format check, tests
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest --tb=short

.PHONY: secrets
secrets:  ## Scan the working tree for committed secrets
	pre-commit run gitleaks --all-files

.PHONY: mongo
mongo:  ## Print the path to the local mongod binary, downloading it if needed
	@./scripts/dev-mongo.sh

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

.PHONY: install-web
install-web:  ## Install frontend dependencies
	npm install

.PHONY: seed
seed:  ## Load demo data and print device tokens for the POS app
	cd backend && uv run python -m app.seed

.PHONY: seed-demo
seed-demo:  ## Load three editions of realistic demo sales for the reports
	cd backend && uv run python -m app.seed_demo

.PHONY: dev-pos
dev-pos:  ## Run the POS app (reachable from a tablet on your wifi)
	npm run dev:pos

.PHONY: test-web
test-web:  ## Run frontend tests
	npm run test --workspace apps/pos

.PHONY: mongo-start
mongo-start:  ## Start a local MongoDB on port 27017 in the background
	@MONGOD=$$(./scripts/dev-mongo.sh) ; \
	mkdir -p .tools/data ; \
	$$MONGOD --dbpath .tools/data --port 27017 --bind_ip 127.0.0.1 --fork \
	         --logpath .tools/mongod.log && echo "MongoDB running on 127.0.0.1:27017"

.PHONY: mongo-stop
mongo-stop:  ## Stop the local MongoDB
	@MONGOD=$$(./scripts/dev-mongo.sh) ; $$MONGOD --dbpath .tools/data --shutdown || true

.PHONY: dev-admin
dev-admin:  ## Run the organiser app on :5174
	npm run dev --workspace apps/admin

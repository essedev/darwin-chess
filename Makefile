.DEFAULT_GOAL := help
API_PORT := 4730

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	cd backend && uv sync
	cd frontend && pnpm install
	cd agent && pnpm install

run-core: ## Run the experiment: orchestrator + referee (needs DARWIN_LLM_API_KEY)
	cd backend && uv run python -m darwin.orchestrator

run-sessions: ## Only N trial sessions, then stop (n=)
	@test -n "$(n)" || (echo "Uso: make run-sessions n=3" && exit 1)
	cd backend && uv run python -m darwin.orchestrator --sessions $(n)

dev: ## Start API + dashboard in parallel
	@trap 'kill 0' EXIT; \
	(cd backend && uv run uvicorn darwin.api.app:app --reload --port $(API_PORT)) & \
	(cd frontend && pnpm dev) & \
	wait

dev-be: ## API only
	cd backend && uv run uvicorn darwin.api.app:app --reload --port $(API_PORT)

dev-fe: ## Dashboard only
	cd frontend && pnpm dev

test: ## Backend tests, including those with real containers (needs make images)
	cd backend && uv run pytest

test-unit: ## Backend tests without Docker
	cd backend && uv run pytest -m "not docker and not llm"

lint: ## Lint backend + frontend, and the language of the prose
	python3 scripts/check-prose.py
	cd backend && uv run ruff check .
	cd frontend && pnpm lint

format: ## Format backend
	cd backend && uv run ruff format .

typecheck: ## Typecheck backend + frontend + pi extension
	cd backend && uv run mypy
	cd frontend && pnpm exec tsc -b
	cd agent && pnpm exec tsc -p .

check: ## Full quality pass
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test

build: ## Build dashboard
	cd frontend && pnpm build

clean: ## Remove build artifacts
	rm -rf frontend/dist frontend/node_modules backend/.venv

db-migrate: ## Apply ledger migrations
	mkdir -p data
	cd backend && uv run alembic upgrade head

db-revision: ## New migration (msg=)
	@test -n "$(msg)" || (echo "Uso: make db-revision msg='descrizione'" && exit 1)
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

lab-build: ## Build the sandbox image
	docker build -t darwin-lab lab

up: ## Production: build the images and start core and api (needs .env with DARWIN_HOME and the key)
	$(MAKE) images
	docker compose --profile run up -d --build

ledger-to-volume: ## Copy data/ledger.sqlite into the ledger volume (once, with core and api stopped)
	sqlite3 data/ledger.sqlite "pragma wal_checkpoint(TRUNCATE)"
	docker run --rm -v darwin-chess_ledger:/ledger -v "$(CURDIR)/data:/src:ro" alpine sh -c 'test ! -e /ledger/ledger.sqlite && cp /src/ledger.sqlite /ledger/'

up-public: ## Like up, plus the Cloudflare tunnel that publishes the dashboard (server only)
	$(MAKE) images
	docker compose --profile run --profile public up -d --build

# The server: DEPLOY_HOST (an ssh host) and DEPLOY_DIR (the repository there, relative to its
# home), in the untracked Makefile.local or on the command line.
-include Makefile.local
DEPLOY_DIR ?= darwin-chess

deploy: ## Copy the code to the server and restart without interrupting the session or the Lichess game (only=api: site only)
	@test -n "$(DEPLOY_HOST)" || { echo "set DEPLOY_HOST in Makefile.local"; exit 1; }
	rsync -az --delete -e "ssh -o BatchMode=yes" --exclude node_modules --exclude .venv \
		--exclude frontend/dist --exclude genome --exclude data --exclude .env --exclude Makefile.local --exclude __pycache__ \
		--exclude .mypy_cache --exclude .ruff_cache --exclude .pytest_cache \
		./ $(DEPLOY_HOST):$(DEPLOY_DIR)/
	ssh -o BatchMode=yes $(DEPLOY_HOST) 'cd $(DEPLOY_DIR) && PATH=/usr/local/bin:$$PATH ONLY=$(only) scripts/restart-drained.sh'

restart-drained: ## On the Compose host: build, drain core, restart core and api
	scripts/restart-drained.sh

down: ## Stop core and api
	docker compose --profile run --profile public down

images: lab-build ## Build all images: sandbox, arena, anchors, test engines
	docker build -t darwin-arena arena
	docker build -t darwin-anchors anchors
	docker build -t darwin-testengines backend/tests/engines

genome-init: lab-build ## Create the empty genome (gen-0) from seed/
	@test ! -e genome || (echo "genome/ esiste già: non lo sovrascrivo" && exit 1)
	mkdir genome
	docker run --rm --network none --user 1000:1000 -e HOME=/tmp -v "$(CURDIR)/genome:/genome" -w /genome darwin-lab sh -c '\
		cargo init --name genome --vcs git . && \
		git config user.name darwin-agent && git config user.email agent@darwin.local'
	cp seed/CONTRACT.md genome/
	cd genome && git add -A && git commit -qm "gen-0: empty seed" && git tag gen-0

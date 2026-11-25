.DEFAULT_GOAL := help
API_PORT := 4730

help: ## Mostra questo help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Installa dipendenze
	cd backend && uv sync
	cd frontend && pnpm install
	cd agent && pnpm install

run-core: ## Avvia l'esperimento: orchestratore + arbitro (serve DARWIN_LLM_API_KEY)
	cd backend && uv run python -m darwin.orchestrator

run-sessions: ## Solo N sessioni di prova e poi si ferma (n=)
	@test -n "$(n)" || (echo "Uso: make run-sessions n=3" && exit 1)
	cd backend && uv run python -m darwin.orchestrator --sessions $(n)

dev: ## Avvia API + dashboard in parallelo
	@trap 'kill 0' EXIT; \
	(cd backend && uv run uvicorn darwin.api.app:app --reload --port $(API_PORT)) & \
	(cd frontend && pnpm dev) & \
	wait

dev-be: ## Solo API
	cd backend && uv run uvicorn darwin.api.app:app --reload --port $(API_PORT)

dev-fe: ## Solo dashboard
	cd frontend && pnpm dev

test: ## Test backend, compresi quelli con container veri (serve make images)
	cd backend && uv run pytest

test-unit: ## Test backend senza Docker
	cd backend && uv run pytest -m "not docker and not llm"

lint: ## Lint backend + frontend
	cd backend && uv run ruff check .
	cd frontend && pnpm lint

format: ## Format backend
	cd backend && uv run ruff format .

typecheck: ## Typecheck backend + frontend + estensione di pi
	cd backend && uv run mypy
	cd frontend && pnpm exec tsc -b
	cd agent && pnpm exec tsc -p .

check: ## Giro completo qualità
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test

build: ## Build dashboard
	cd frontend && pnpm build

clean: ## Pulisce artefatti di build
	rm -rf frontend/dist frontend/node_modules backend/.venv

db-migrate: ## Applica migrazioni del ledger
	mkdir -p backend/data
	cd backend && uv run alembic upgrade head

db-revision: ## Nuova migrazione (msg=)
	@test -n "$(msg)" || (echo "Uso: make db-revision msg='descrizione'" && exit 1)
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

lab-build: ## Costruisce l'immagine del sandbox
	docker compose build lab

images: lab-build ## Costruisce tutte le immagini: sandbox, arena, ancore, motori di test
	docker build -t darwin-arena arena
	docker build -t darwin-anchors anchors
	docker build -t darwin-testengines backend/tests/engines

genome-init: lab-build ## Crea il genoma vuoto (gen-0) da seed/
	@test ! -e genome || (echo "genome/ esiste già: non lo sovrascrivo" && exit 1)
	mkdir genome
	docker compose run --rm --no-deps lab sh -c '\
		cargo init --name genome --vcs git . && \
		git config user.name darwin-agent && git config user.email agent@darwin.local'
	cp seed/CONTRACT.md genome/
	cd genome && git add -A && git commit -qm "gen-0: empty seed" && git tag gen-0

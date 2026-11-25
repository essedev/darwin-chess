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
	mkdir -p data
	cd backend && uv run alembic upgrade head

db-revision: ## Nuova migrazione (msg=)
	@test -n "$(msg)" || (echo "Uso: make db-revision msg='descrizione'" && exit 1)
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

lab-build: ## Costruisce l'immagine del sandbox
	docker build -t darwin-lab lab

up: ## Produzione: costruisce le immagini e avvia core e api (serve .env con DARWIN_HOME e la chiave)
	$(MAKE) images
	docker compose --profile run up -d --build

ledger-to-volume: ## Copia data/ledger.sqlite nel volume del registro (una volta, con core e api fermi)
	sqlite3 data/ledger.sqlite "pragma wal_checkpoint(TRUNCATE)"
	docker run --rm -v darwin-chess_ledger:/ledger -v "$(CURDIR)/data:/src:ro" alpine sh -c 'test ! -e /ledger/ledger.sqlite && cp /src/ledger.sqlite /ledger/'

up-public: ## Come up, più il tunnel Cloudflare che pubblica la dashboard (solo su server)
	$(MAKE) images
	docker compose --profile run --profile public up -d --build

DEPLOY_HOST ?= server
DEPLOY_DIR ?= darwin-chess

deploy: ## Porta il codice su server e riavvia senza interrompere sessione e partita Lichess (only=api: solo il sito)
	rsync -az --delete -e "ssh -o BatchMode=yes" --exclude node_modules --exclude .venv \
		--exclude frontend/dist --exclude genome --exclude data --exclude .env --exclude __pycache__ \
		--exclude .mypy_cache --exclude .ruff_cache --exclude .pytest_cache \
		./ $(DEPLOY_HOST):$(DEPLOY_DIR)/
	ssh -o BatchMode=yes $(DEPLOY_HOST) 'cd $(DEPLOY_DIR) && PATH=/usr/local/bin:$$PATH ONLY=$(only) scripts/restart-drained.sh'

restart-drained: ## Sull'host di Compose: build, svuota core, riavvia core e api
	scripts/restart-drained.sh

down: ## Ferma core e api
	docker compose --profile run --profile public down

images: lab-build ## Costruisce tutte le immagini: sandbox, arena, ancore, motori di test
	docker build -t darwin-arena arena
	docker build -t darwin-anchors anchors
	docker build -t darwin-testengines backend/tests/engines

genome-init: lab-build ## Crea il genoma vuoto (gen-0) da seed/
	@test ! -e genome || (echo "genome/ esiste già: non lo sovrascrivo" && exit 1)
	mkdir genome
	docker run --rm --network none --user 1000:1000 -e HOME=/tmp -v "$(CURDIR)/genome:/genome" -w /genome darwin-lab sh -c '\
		cargo init --name genome --vcs git . && \
		git config user.name darwin-agent && git config user.email agent@darwin.local'
	cp seed/CONTRACT.md genome/
	cd genome && git add -A && git commit -qm "gen-0: empty seed" && git tag gen-0

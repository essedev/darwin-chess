# darwin-chess

Un agente LLM scrive da zero un motore di scacchi e lo fa evolvere da solo: ogni modifica sopravvive solo se vince contro la versione precedente, giudicata da un arbitro che l'agente non può toccare.

## Come funziona

- **genome/**: il motore in Rust, di proprietà dell'agente. È un repo git a parte: ogni commit è una generazione che ha vinto.
- **Arbitro**: codice fidato che verifica le regole (perft), fa giocare le partite, decide con un test statistico (SPRT) e misura l'Elo contro ancore fisse.
- **Orchestratore**: il ciclo dell'agente (Claude Haiku 5.5, via Anthropic o OpenRouter) con un tetto di spesa giornaliero.
- **Dashboard**: partita live, curva Elo, storia delle generazioni, ragionamento dell'agente, spesa; bilingue, con il bot Lichess e i commenti alle partite.

La divisione dei ruoli è dichiarata: l'LLM costruisce e ottimizza la macchina, la rete di valutazione impara gli scacchi dalle partite del motore contro se stesso.

## Stack

- Backend: Python 3.13, FastAPI, SQLAlchemy 2.0 async, Alembic, python-chess (gestito con uv)
- Frontend: React 19, TypeScript strict, Vite, Tailwind v4, shadcn/ui, TanStack Query (gestito con pnpm)
- Motore: Rust, compilato ed eseguito solo dentro il sandbox Docker
- Registro: SQLite
- Infra: Docker Compose, esecuzione 24/7 su un MacBook Air (server), sito pubblico su https://darwin.esse.dev

## Setup rapido

```bash
make install
cp .env.example .env           # alla radice; poi DARWIN_HOME e DARWIN_LLM_API_KEY
make db-migrate
make genome-init               # crea il genoma vuoto (gen-0)
make dev                       # API su :4730, dashboard su :4731
```

## Documentazione

- [Architettura](docs/ARCHITECTURE.md)
- [Schema del registro](docs/DATABASE_SCHEMA.md)
- [Convenzioni di codice](docs/CONVENTIONS.md)
- [Decisioni](docs/DECISIONS.md)
- [Roadmap](docs/ROADMAP.md)

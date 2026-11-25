# darwin-chess - Istruzioni per Claude

## Cos'è

Un agente LLM (Haiku 5.5 via OpenRouter) scrive da zero un motore di scacchi in Rust e lo evolve da solo; un arbitro fidato decide quali generazioni sopravvivono. Esecuzione 24/7 su server. Visione e confini in `docs/ARCHITECTURE.md`.

## Stack

- Backend `backend/`: Python 3.13 + uv, package `darwin` (`referee`, `orchestrator`, `ledger`, `api`), FastAPI, SQLAlchemy 2.0 async su SQLite, Alembic, python-chess.
- Frontend `frontend/`: React 19 + TS strict + Vite + Tailwind v4 + shadcn/ui + TanStack Query.
- Sandbox `lab/`: immagine Docker con Rust, senza rete. Genoma in `genome/` (repo git separato, ignorato).
- Arena `arena/`: immagine con fastchess (versione fissata) e la CLI di Docker; gioca le partite creando un container per motore. Ancore `anchors/`: giocatore casuale su python-chess; `backend/tests/engines/` ci costruisce sopra i motori difettosi dei test.
- Agente (M3): pi in modalità RPC, versione fissata, con un'estensione TypeScript per i tool nostri.
- Porte (portsage): API 4730, Vite 4731.

## Comandi

- `make install`, `make dev` (API + dashboard), `make check` (format, lint, typecheck, test)
- `make db-migrate`, `make db-revision msg='...'`
- `make run-core` (esperimento), `make run-sessions n=3` (sessioni di prova): servono `DARWIN_LLM_API_KEY` e `make genome-init`
- `make lab-build`, `make genome-init` (crea `gen-0` da `seed/`, rifiuta se `genome/` esiste)
- `make images` (sandbox, arena, ancore, motori di test): serve prima di `make test`, che gira anche i test con container veri (marker `docker`, circa un minuto); `make test-unit` li salta

## Regole del progetto

- **Il confine di fiducia non si attraversa**: niente codice dell'arbitro nel sandbox, niente binari del genoma eseguiti sull'host, l'arbitro non importa da `orchestrator` o `api`. Ogni cosa che indebolisce l'isolamento va discussa prima.
- **Il genoma è dell'agente**: non modificare `genome/` a mano. Per cambiare cosa riceve un genoma nuovo si edita `seed/`.
- **Spesa LLM**: ogni run che chiama il modello costa. I test LLM stanno dietro il marker `llm`; un batch di iterazioni si lancia solo dopo aver misurato il costo su un campione e averlo fatto approvare.
- File rivolti all'agente (`seed/*.md`, prompt) in inglese; doc per umani in italiano.

## Gotcha

- TypeScript 7: `baseUrl` non esiste più, gli alias usano solo `paths`.
- `uv init --package` non crea `py.typed`: mypy usa `files = ["src", "tests"]`.
- Nell'immagine `rust` il `CARGO_HOME` è `/usr/local/cargo`, non `~/.cargo`; il sandbox è offline (`CARGO_NET_OFFLINE`), quindi niente crate scaricati.
- Alembic su SQLite: `render_as_batch=True` già attivo in `alembic/env.py`.
- I container creati dall'arbitro montano i dati allo stesso path dell'host (`DARWIN_DATA_DIR`, assoluto): un path relativo o diverso rompe i bind mount quando `core` gira in container.
- server è un MacBook Air M4 senza ventola, non un Mac mini: sotto carico continuo rallenta.
- pi risolve i percorsi relativi sulla propria cartella dell'host: l'estensione (`agent/darwin-extension.ts`) li traduce in `/genome` prima di ogni `docker exec`. pi va sempre avviato con i flag di `orchestrator/pi.py` (niente caricamento automatico).
- Il test `tests/orchestrator/test_docker_session.py` gira pi vero contro un modello finto: rompe se cambia il protocollo RPC o l'API delle estensioni di pi, ed è il primo controllo da fare quando si aggiorna pi.
- fastchess aspetta 60 secondi fissi un motore che ignora `quit`: per questo ogni motore passa da `arena/engine_shim.py`, che dopo 2 secondi elimina il container. L'immagine arena ha solo `python3-minimal` (niente `uuid`, per esempio).
- I container dei motori sopravvivono al loro client: ogni run porta l'etichetta `darwin.run=<id>` e si ripulisce per etichetta, anche quando fallisce.

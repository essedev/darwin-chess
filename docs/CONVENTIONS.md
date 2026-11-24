# Convenzioni di codice

Regole specifiche di questo progetto. Per gli standard trasversali vedi il CLAUDE.md globale.

## Generali

- Line length 100. Identificatori e commenti in inglese, testi della dashboard in italiano.
- Prosa per umani (README, `docs/`) in italiano. File rivolti all'agente (`seed/*.md`, prompt in `darwin.orchestrator`) in inglese.
- Filename: `snake_case` in Python, `kebab-case` in frontend.

## Backend Python

- Type hints ovunque, mypy strict verde.
- Async per tutto l'I/O: database, subprocess dei motori, chiamate LLM.
- Errori tipizzati per dominio (`RefereeError`, `BudgetExceeded`, ...). Mai `except: pass`: un errore inatteso chiude l'esperimento con `status = error` e il traceback nel registro.
- Logging strutturato con `logging`, un logger per modulo. Gli eventi che la dashboard mostra vanno in `agent_events`, non nei log.
- Configurazione solo da `darwin.config.Settings` (variabili `DARWIN_*`), mai `os.environ` sparsi.
- Max ~300 righe per file.

## Arbitro

- Nessun import da `darwin.orchestrator` o `darwin.api`: riceve un binario e restituisce un verdetto.
- Ogni processo motore gira nel proprio container effimero: niente esecuzione di binari del genoma sull'host.
- Il dettaglio mostrato all'agente è esplicito (`detail` pubblico), mai output interno grezzo.

## Frontend React

- Componenti funzionali, feature in `src/features/<nome>/` con i propri hook.
- TanStack Query per lo stato server, `EventSource` per il live, `useState` per lo stato UI.
- Icone solo Lucide (`lucide-react`, lo stesso set dei componenti shadcn): un solo spessore del tratto, 16 px nel testo e 20 px nei controlli, e solo dove aggiungono significato.
- Pezzi degli scacchi: set cburnett, SVG in `frontend/public/pieces/cburnett/` con il file di licenza (GPLv2+, Colin M.L. Burnett); niente caricamento da CDN esterni.
- Ogni vista gestisce loading, empty, error e success.
- `cursor-pointer` esplicito sugli elementi interattivi (Tailwind v4 lo toglie dai button).
- Niente `max-width` sui contenuti. Mobile curato dalla prima schermata.
- Max ~200 righe per componente.

## Test

- Backend: pytest. Integration sul registro SQLite vero in una cartella temporanea, mai mock del database.
- Arbitro: i test girano contro un motore UCI vero (un motore di riferimento nel sandbox), non contro risposte finte.
- Chiamate LLM solo dietro il marker `llm` ed esclusive dei run espliciti: costano.
- Frontend: solo componenti critici.

## Pulizia

- Niente codice morto, niente TODO senza riferimento in `ROADMAP.md`.
- Il nuovo codice rispetta queste regole; il vecchio si sistema quando si tocca l'area.

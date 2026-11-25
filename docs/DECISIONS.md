# Decisioni

## 2026-11-24: l'LLM costruisce la macchina, la rete impara gli scacchi

Haiku conosce a memoria le tecniche dei motori (alfa-beta, transposition table, NNUE), quindi un motore scritto solo da lui misura la capacità di applicare conoscenza nota, non di scoprire. La valutazione la impara invece una rete dalle partite del motore contro se stesso, partendo da zero: quello che sa viene dai dati. Architettura libera per l'agente, con il vincolo di un budget di CPU per generazione: in pratica porta allo stile Stockfish (alfa-beta + NNUE in CPU).

## 2026-11-24: arbitro immutabile, motori in container effimeri

L'agente ha pieno controllo sul genoma ma nessun accesso all'arbitro. Ogni processo motore gira in un container proprio (`--network none`, 1 CPU, binario in sola lettura): nello stesso container un candidato potrebbe terminare il processo avversario. Il perft si verifica su posizioni casuali perché i conteggi delle posizioni standard sono noti e si possono scrivere a mano.

## 2026-11-24: SQLite invece di PostgreSQL

Un solo scrittore su una sola macchina, nessun accesso concorrente da altri servizi: Postgres aggiungerebbe un servizio senza alcun vantaggio. SQLAlchemy e Alembic restano, quindi la migrazione sarebbe meccanica.

## 2026-11-24: registro append-only, niente soft delete

Il registro è la storia dell'esperimento: nessuna riga si cancella, quindi `deleted_at` non avrebbe un caso d'uso.

## 2026-11-24: Haiku 5.5 via OpenRouter, provider intercambiabile

Iterazione stimata intorno a 1 centesimo, tetto 2 $/giorno. Il client usa l'API compatibile OpenAI, quindi un modello locale (llama-server, LM Studio) o un altro provider è una variabile d'ambiente. Il confronto fra modelli economici è rimandato: si fa se Haiku rende poco.

## 2026-11-24: Lichess come misura esterna, non come filtro

Le partite su Lichess sono troppo lente per decidere le generazioni (centinaia al giorno contro migliaia necessarie), ma danno un rating che l'agente non può falsificare. Chess.com è escluso: non ammette bot.

## 2026-11-24: dashboard in stile diretta essenziale (concept D)

Su quattro direzioni (laboratorio denso, genealogia editoriale, diretta da secondo schermo, diretta essenziale) la scelta è D: scacchiera al centro con i due giocatori e lo storico delle mosse, sottotitoli dell'agente, generazione corrente in evidenza in alto, storia delle generazioni a sinistra, a destra solo due carte (SPRT in parole semplici, spesa). Scartate A (troppi elementi per uno schermo da guardare), B (la storia da sola non dice cosa succede adesso: resta come spunto per una pagina secondaria) e C (stesso spirito di D, ma con più rumore). Il concept è in `docs/concepts/concept-a-dashboard.html`.

## 2026-11-24: pezzi cburnett e icone Lucide

Pezzi cburnett, il set classico di Lichess e Wikipedia, scelto a vista fra sette set con licenza verificata nel COPYING.md di lila. È GPLv2+: va bene per un progetto personale, ma se il repo diventasse pubblico con un'altra licenza gli SVG restano GPL e vanno dichiarati a parte. Icone Lucide perché sono già il set dei componenti shadcn: un secondo set sarebbe incoerente.

## 2026-11-25: le sconfitte su Lichess diventano lezioni per l'agente

Il bot Lichess gioca sempre con il campione in carica e ogni sconfitta entra in una coda che l'agente legge, riassunta, prima di ogni iterazione: avversari veri trovano debolezze che il gioco contro se stesso non mostra. Le partite perse le analizza Stockfish lato arbitro, che indica la mossa in cui la valutazione crolla ma non la soluzione. È un aiuto esterno dichiarato: la rete continua a imparare solo dalle partite del motore. L'alternativa scartata, dare all'agente solo partita e risultato, renderebbe il feedback molto più povero. Il giudizio sui candidati resta all'arbitro in locale.

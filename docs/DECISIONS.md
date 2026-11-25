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

## 2026-11-25: fastchess gioca, l'arbitro giudica

Le partite le gioca fastchess (versione fissata, compilata nell'immagine `arena`): controllo del tempo, concorrenza, crash e PGN sono problemi già risolti, riscriverli non darebbe niente. Il giudizio resta nostro: l'arbitro rilegge ogni PGN con python-chess e calcola l'SPRT pentanomiale a lotti, fermandosi quando il rapporto di verosimiglianza supera una soglia. L'SPRT interno di fastchess non si usa, così il verdetto ha una sola fonte. Il libro di aperture lo genera l'arbitro (mosse casuali a materiale pari) finché non c'è Stockfish per filtrarlo.

## 2026-11-25: pi come harness dell'agente, in modalità RPC

L'agente gira dentro pi, comandato dall'orchestratore via JSON su stdin e stdout. Rispetto al ciclo scritto da noi porta tool di modifica dei file già rodati, che per un modello piccolo contano molto, e il supporto a OpenRouter. I comandi di pi vengono eseguiti nel sandbox, la chiave API resta fuori. Costi accettati: Node nello stack e un progetto giovane, quindi versione fissata. Scartato il Claude Agent SDK: prompt di sistema pesante pagato a ogni chiamata e legame con un solo fornitore. Sostituisce il client compatibile OpenAI previsto il 24/11; la stima di spesa sale a 2-5 centesimi per iterazione, da misurare.

## 2026-11-25: tool standard più quattro nostri

L'agente ha `read`, `write`, `edit`, `bash` nel sandbox e quattro tool nostri (`perft_check`, `submit`, `experiments`, `run_job`, poi `lichess_losses`) in un'estensione TypeScript che inoltra all'API locale dell'orchestratore. Diventa un tool solo ciò che il sandbox non può fare: interrogare l'arbitro, leggere il registro, agire fuori dal sandbox. Pochi tool perché le descrizioni viaggiano a ogni chiamata e un modello piccolo sceglie meglio fra poche opzioni chiare.

## 2026-11-25: ritmi a eventi e spesa distribuita sulle ore

La CPU lavora sempre (partite, self-play), l'LLM si sveglia sugli eventi (verdetto, fine di un job, sconfitte Lichess) e una volta ogni tanto riscrive la propria strategia. Il budget di 2 $ al giorno si spende a quote orarie: un risveglio senza quota aspetta, la macchina no. Scartato il risveglio a orario fisso: o spreca chiamate quando non è cambiato niente, o lascia la CPU ferma.

## 2026-11-25: deploy in Compose con container effimeri, dati allo stesso path

Su server girano due servizi fissi, `core` (orchestratore e arbitro nello stesso processo, così il registro ha un solo scrittore) e `api`; sandbox, compilazioni, arena, motori e job sono container effimeri creati da `core`. Un solo container non basterebbe: ogni motore deve stare isolato dall'avversario. I dati sono montati allo stesso path dell'host, così i bind mount dei container figli funzionano uguali in sviluppo e in produzione. server è un MacBook Air M4 senza ventola, non un Mac mini: la concorrenza delle partite si tara con un test di carico prima di fidarsi delle stime.

## 2026-11-25: mirror fidato e memoria fuori dal genoma

Il repository del genoma è dell'agente: può riscrivere tag, cancellare oggetti, aggiungere hook o una `core.fsmonitor` che git eseguirebbe sull'host. Per questo git non gira mai sull'host sul genoma, e la storia che conta vive in un mirror bare che scrive solo l'orchestratore: l'arbitro compila da lì e ogni sessione riparte da lì. `NOTES.md` e `STRATEGY.md` escono dal genoma e vanno in `/memory`: dentro il genoma una lezione imparata da un esperimento bocciato sparirebbe con il reset.

## 2026-11-25: test della sessione completa con un modello finto

La catena pi, estensione, sandbox, tool, mirror, arbitro e registro si prova senza spendere: un endpoint locale compatibile OpenAI risponde con un copione di chiamate ai tool, configurato in pi come provider. Il costo per chiamata arriva da pi stesso, che lo calcola dai prezzi del modello: lo stesso campo usato con OpenRouter.


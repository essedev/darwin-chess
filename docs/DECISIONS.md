# Decisioni

Voci numerate, citabili come `#N`. Ogni voce dice cosa vincola e perché, con le alternative scartate; il come sta in `ARCHITECTURE.md` e nel codice, la cronaca in `CYCLES.md`. Status: `proposta`, `attiva`, `in parte superata da #M` (la voce riporta già la regola in vigore), `superata da #M` (spostata in `decisions-archive.md`).

## #1 L'LLM costruisce la macchina, la rete impara gli scacchi

Status: attiva. Data: 2026-11-24.

Haiku conosce a memoria le tecniche dei motori (alfa-beta, transposition table, NNUE), quindi un motore scritto solo da lui misura la capacità di applicare conoscenza nota, non di scoprire. La valutazione la impara invece una rete dalle partite del motore contro se stesso, partendo da zero: quello che sa viene dai dati. Architettura libera per l'agente, con il vincolo di un budget di CPU per generazione: in pratica porta allo stile Stockfish (alfa-beta + NNUE in CPU).

## #2 Arbitro immutabile, motori in container effimeri

Status: attiva. Data: 2026-11-24.

L'agente ha pieno controllo sul genoma ma nessun accesso all'arbitro. Ogni processo motore gira in un container proprio (`--network none`, 1 CPU, binario in sola lettura): nello stesso container un candidato potrebbe terminare il processo avversario. Il perft si verifica su posizioni casuali perché i conteggi delle posizioni standard sono noti e si possono scrivere a mano.

## #3 SQLite invece di PostgreSQL

Status: attiva. Data: 2026-11-24.

Un solo scrittore su una sola macchina, nessun accesso concorrente da altri servizi: Postgres aggiungerebbe un servizio senza alcun vantaggio. SQLAlchemy e Alembic restano, quindi la migrazione sarebbe meccanica.

## #4 Registro append-only, niente soft delete

Status: attiva. Data: 2026-11-24.

Il registro è la storia dell'esperimento: nessuna riga si cancella, quindi `deleted_at` non avrebbe un caso d'uso.

## #5 Haiku 5.5 via OpenRouter, provider intercambiabile

Status: in parte superata da #11 e #17. Data: 2026-11-24.

Iterazione stimata fra 2 e 5 centesimi, da misurare (da #11), tetto 2 $/giorno. Provider e modello sono configurazione di pi, quindi un modello locale (llama-server, LM Studio) o un altro provider è una variabile d'ambiente (da #11). Il confronto fra modelli economici è rimandato: si fa se Haiku rende poco.

## #6 Lichess come misura esterna, non come filtro

Status: attiva. Data: 2026-11-24.

Le partite su Lichess sono troppo lente per decidere le generazioni (centinaia al giorno contro migliaia necessarie), ma danno un rating che l'agente non può falsificare. Chess.com è escluso: non ammette bot.

## #7 Dashboard in stile diretta essenziale (concept D)

Status: attiva. Data: 2026-11-24.

Su quattro direzioni (laboratorio denso, genealogia editoriale, diretta da secondo schermo, diretta essenziale) la scelta è D: scacchiera al centro con i due giocatori e lo storico delle mosse, sottotitoli dell'agente, generazione corrente in evidenza in alto, storia delle generazioni a sinistra, a destra solo due carte (SPRT in parole semplici, spesa). Scartate A (troppi elementi per uno schermo da guardare), B (la storia da sola non dice cosa succede adesso: resta come spunto per una pagina secondaria) e C (stesso spirito di D, ma con più rumore). Il concept è in `docs/concepts/concept-a-dashboard.html`.

## #8 Pezzi cburnett e icone Lucide

Status: attiva. Data: 2026-11-24.

Pezzi cburnett, il set classico di Lichess e Wikipedia, scelto a vista fra sette set con licenza verificata nel COPYING.md di lila. È GPLv2+: va bene per un progetto personale, ma se il repo diventasse pubblico con un'altra licenza gli SVG restano GPL e vanno dichiarati a parte. Icone Lucide perché sono già il set dei componenti shadcn: un secondo set sarebbe incoerente.

## #9 Le sconfitte su Lichess diventano lezioni per l'agente

Status: attiva. Data: 2026-11-25.

Il bot Lichess gioca sempre con il campione in carica e ogni sconfitta entra in una coda che l'agente legge, riassunta, prima di ogni iterazione: avversari veri trovano debolezze che il gioco contro se stesso non mostra. Le partite perse le analizza Stockfish lato arbitro, che indica la mossa in cui la valutazione crolla ma non la soluzione. È un aiuto esterno dichiarato: la rete continua a imparare solo dalle partite del motore. L'alternativa scartata, dare all'agente solo partita e risultato, renderebbe il feedback molto più povero. Il giudizio sui candidati resta all'arbitro in locale.

## #10 fastchess gioca, l'arbitro giudica

Status: attiva. Data: 2026-11-25.

Le partite le gioca fastchess (versione fissata, compilata nell'immagine `arena`): controllo del tempo, concorrenza, crash e PGN sono problemi già risolti, riscriverli non darebbe niente. Il giudizio resta nostro: l'arbitro rilegge ogni PGN con python-chess e calcola l'SPRT pentanomiale a lotti, fermandosi quando il rapporto di verosimiglianza supera una soglia. L'SPRT interno di fastchess non si usa, così il verdetto ha una sola fonte. Il libro di aperture lo genera l'arbitro (mosse casuali a materiale pari) finché non lo sostituisce un libro filtrato da Stockfish.

## #11 pi come harness dell'agente, in modalità RPC

Status: attiva. Data: 2026-11-25.

L'agente gira dentro pi, comandato dall'orchestratore via JSON su stdin e stdout. Rispetto al ciclo scritto da noi porta tool di modifica dei file già rodati, che per un modello piccolo contano molto, e il supporto a OpenRouter. I comandi di pi vengono eseguiti nel sandbox, la chiave API resta fuori. Costi accettati: Node nello stack e un progetto giovane, quindi versione fissata. Scartato il Claude Agent SDK: prompt di sistema pesante pagato a ogni chiamata e legame con un solo fornitore. Sostituisce il client compatibile OpenAI previsto in #5; la stima di spesa sale a 2-5 centesimi per iterazione, da misurare.

## #12 Tool standard più quattro nostri

Status: attiva. Data: 2026-11-25.

L'agente ha `read`, `write`, `edit`, `bash` nel sandbox e quattro tool nostri (`perft_check`, `submit`, `experiments`, `run_job`, poi `lichess_losses`) in un'estensione TypeScript che inoltra all'API locale dell'orchestratore. Diventa un tool solo ciò che il sandbox non può fare: interrogare l'arbitro, leggere il registro, agire fuori dal sandbox. Pochi tool perché le descrizioni viaggiano a ogni chiamata e un modello piccolo sceglie meglio fra poche opzioni chiare.

## #13 Ritmi a eventi e spesa distribuita sulle ore

Status: attiva. Data: 2026-11-25.

La CPU lavora sempre (partite, self-play), l'LLM si sveglia sugli eventi (verdetto, fine di un job, sconfitte Lichess) e una volta ogni tanto riscrive la propria strategia. Il budget di 2 $ al giorno si spende a quote orarie: un risveglio senza quota aspetta, la macchina no. Scartato il risveglio a orario fisso: o spreca chiamate quando non è cambiato niente, o lascia la CPU ferma.

## #14 Deploy in Compose con container effimeri, dati allo stesso path

Status: attiva. Data: 2026-11-25.

Su server girano due servizi fissi, `core` (orchestratore e arbitro nello stesso processo, così il registro ha un solo scrittore) e `api`; sandbox, compilazioni, arena, motori e job sono container effimeri creati da `core`. Un solo container non basterebbe: ogni motore deve stare isolato dall'avversario. I dati sono montati allo stesso path dell'host, così i bind mount dei container figli funzionano uguali in sviluppo e in produzione. server è un MacBook Air M4 senza ventola, non un Mac mini: la concorrenza delle partite si tara con un test di carico prima di fidarsi delle stime.

## #15 Mirror fidato e memoria fuori dal genoma

Status: attiva. Data: 2026-11-25.

Il repository del genoma è dell'agente: può riscrivere tag, cancellare oggetti, aggiungere hook o una `core.fsmonitor` che git eseguirebbe sull'host. Per questo git non gira mai sull'host sul genoma, e la storia che conta vive in un mirror bare che scrive solo l'orchestratore: l'arbitro compila da lì e ogni sessione riparte da lì. `NOTES.md` e `STRATEGY.md` escono dal genoma e vanno in `/memory`: dentro il genoma una lezione imparata da un esperimento bocciato sparirebbe con il reset.

## #16 Test della sessione completa con un modello finto

Status: attiva. Data: 2026-11-25.

La catena pi, estensione, sandbox, tool, mirror, arbitro e registro si prova senza spendere: un endpoint locale compatibile OpenAI risponde con un copione di chiamate ai tool, configurato in pi come provider. Il costo per chiamata arriva da pi stesso, che lo calcola dai prezzi del modello: lo stesso campo usato con OpenRouter.

## #17 Provider Anthropic o OpenRouter, Anthropic di default

Status: attiva. Data: 2026-11-25.

La chiave disponibile è Anthropic, quindi il default diventa Anthropic diretto; OpenRouter resta selezionabile con `DARWIN_LLM_PROVIDER`. Il cambio non tocca altro codice: pi conosce entrambi i provider, ciascuno con il suo ID del modello (`claude-haiku-5-5`, `anthropic/claude-haiku-5.5`) e la sua variabile per la chiave, e calcola il costo dagli stessi prezzi (0,10 $ e 0,50 $ per milione di token, cache in lettura 0,01 $). Supera la scelta di OpenRouter di #5.

## #18 Librerie per l'agente, niente GPU, quota disco sul disco interno

Status: attiva. Data: 2026-11-25.

L'agente riceve poche crate Rust già scaricate (rand, rayon, bytemuck) e Python con PyTorch CPU e numpy, tutto dentro l'immagine e quindi offline. Senza librerie l'addestramento di una rete andrebbe scritto da zero in Rust, il punto in cui un modello economico rischia di arenarsi; con PyTorch è il percorso standard, lo stesso di Stockfish che addestra in PyTorch e incorpora la rete nel motore. Quello che la rete sa viene comunque dalle partite. Il motore resta in Rust e i pesi vanno incorporati nel binario, perché l'arbitro lo esegue da solo.

Niente GPU: Docker su Mac non vede la GPU Apple, e usarla vorrebbe dire eseguire codice dell'agente su macOS fuori dal sandbox. Scartato anche un addestratore nostro a cui l'agente passa solo dati: l'agente configurerebbe invece di costruire. Per reti piccole stile NNUE la CPU basta; si riapre se l'addestramento diventa il collo di bottiglia.

I job scrivono sul disco interno di server (120 GB liberi) con una quota di 10 GB per job e 40 GB in tutto: un job oltre la quota viene fermato, uno nuovo viene rifiutato a quota piena, e l'agente cancella da sé gli output vecchi. Scartato il disco esterno: è condiviso con la libreria di other services, quasi pieno, e collegato via cavo, quindi può sparire sotto `core`.


## #19 In Compose il registro sta in un volume Docker; ogni container porta l'istanza

Status: attiva. Data: 2026-11-25.

Il primo avvio su server ha mostrato connessioni SQLite che non vedevano righe appena scritte da un'altra connessione dello stesso processo, con errori di chiave esterna e `core` riavviato. La causa è la cartella condivisa di Docker Desktop: la memoria condivisa del WAL non vi resta coerente, il caso dei filesystem di rete che SQLite sconsiglia. Il registro passa a un volume Docker, dentro la macchina virtuale; il resto di `data/` resta in cartella perché va montato nei container dei motori allo stesso path. Scartato il journal classico senza WAL: si appoggia ai lock dei file, che sulla stessa condivisione non danno più garanzie.

Fermare `core` lasciava accesi arena, motori e sandbox. Ogni container porta ora l'etichetta dell'istanza (`prod` in Compose, `dev` in sviluppo, una propria per i test) e all'avvio `core` rimuove quelli della sua istanza, senza toccare gli altri.

## #20 Sito pubblico e bilingue, commenti per i visitatori separati dall'agente

Status: attiva. Data: 2026-11-25.

La dashboard diventa pubblica (Cloudflare Tunnel su `darwin.esse.dev`) e bilingue, italiano e inglese. Codice, prompt e testi dell'agente restano in inglese: ipotesi e lezioni vengono tradotte in italiano una volta e conservate, i pensieri in diretta e i file della memoria restano originali con un'etichetta, perché tradurre ogni pensiero costerebbe di più e arriverebbe in ritardo.

I commenti leggibili su partite e verdetti li scrive Haiku a partire da dati verificati (valutazioni di Stockfish, statistiche dei match), mai interpretando la partita a occhio. Hanno un budget loro, 0,20 $ al giorno, e l'agente non li legge: un secondo modello che gli spiega le partite cambierebbe la natura dell'esperimento. Il commento dell'arbitro arriva a match finito e non a intervalli di partite, perché a metà match i numeri ballano e il testo direbbe cose che il verdetto poi smentisce.

## #21 Diretta a colonne bilanciate ed Elo con il suo margine

Status: attiva. Data: 2026-11-25.

La revisione di Diretta ed Evoluzione segue il concept B (`docs/concepts/concept-b-revisione.html`): per la Diretta la variante a1 (Rifinita), per l'Evoluzione la A. Scartate B (la Diretta come partita più un riquadro, la storia raggruppata per generazione) e C (una colonna sola come notiziario), che cambiavano la struttura per risolvere un problema di quantità e di scrittura; scartate le versioni estetiche a2 (senza riquadri) e a3 (griglia da strumento).

La Diretta non contiene niente che cresce con la storia: tre colonne che finiscono alla stessa altezza, le ultime cinque generazioni, gli ultimi tre risultati fissi con il rinvio all'Evoluzione o al profilo del bot su Lichess. "Mostra altri" sul posto è stato provato e tolto: allungava una colonna e sbilanciava di nuovo la pagina.

Il numero principale della forza è l'Elo assoluto contro Stockfish con il suo margine al 95%, e il grafico mostra le barre d'errore e la fascia dove le generazioni si sovrappongono. I margini veri (± 120-140 Elo con le partite di oggi) mostravano che il calo da 1.193 a 1.129 era rumore, mentre il sito lo presentava come una discesa accanto a guadagni di +24 e +42. Il guadagno sul campione precedente resta, secondario e spiegato; la performance su Lichess si mostra da cinque partite in su.

I titoli brevi degli esperimenti li scrive il worker dei commenti alla consegna, come la traduzione, non l'agente: il lavoro dell'agente non cambia e i titoli restano fuori da quello che legge.


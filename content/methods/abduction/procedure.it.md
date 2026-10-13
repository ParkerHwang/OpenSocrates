## Purpose

Usa questa procedura per confrontare spiegazioni concorrenti di un fatto osservato o sorprendente e scegliere la migliore spiegazione attuale senza presentarla come dimostrata. Richiede almeno due candidati ancora plausibili, valuta adeguatezza esplicativa e rischio e identifica prove che li distinguano. Il risultato è una diagnosi provvisoria con un controllo successivo concreto, non un'autorizzazione ad adattare i fatti alla storia preferita.

## Use when

Usala per debug, diagnosi, indagini, interpretazione di anomalie e altre situazioni in cui diverse cause possono spiegare la stessa osservazione. È adatta a informazioni incomplete e domande su ciò che probabilmente accade o sul motivo di un risultato inatteso. Usala quando una regola deduttiva non determina già il risultato.

## Do not use when

Non usarla quando regole esplicite e premesse accertate implicano la conclusione, o nessuna osservazione può distinguere le spiegazioni. Non trattare un unico candidato come un insieme di spiegazioni, non attribuire precisione inventata a una storia e non considerare l'assenza di osservazioni contrarie come conferma. Evita certezze causali quando i candidati sono soltanto interpretazioni descrittive.

## Inputs to establish

Stabilisci l'osservazione sorprendente, il riferimento atteso, la decisione o diagnosi interessata, i fatti noti, le spiegazioni plausibili e le prove o fonti disponibili. Specifica se ciascun candidato è una causa, un meccanismo, un errore nei dati o una spiegazione legata all'ambito. Fai al massimo una domanda decisiva se l'osservazione o l'obiettivo decisionale è poco chiaro; altrimenti procedi con ipotesi esplicite.

## Procedure

1. Pubblica l'osservazione da spiegare e il riferimento che contraddice. Distingui fatti controllati, resoconti dell'utente e ipotesi: questo crea lo stato visibile dell'anomalia.
2. Pubblica almeno due spiegazioni candidate con osservazioni previste e ambito. Aggiungi un candidato relativo a errori di misura, selezione o rendicontazione quando plausibile, senza privilegiare automaticamente la prima spiegazione sostanziale.
3. Pubblica un confronto qualitativo di adeguatezza esplicativa, copertura, semplicità, coerenza con conoscenze accertate e verificabilità. Usa etichette ordinali come forte, moderato, debole o sconosciuto; non inventare probabilità.
4. Pubblica le prove discriminanti: osservazione, esperimento o fonte capace di separare i candidati principali. Specifica quale esito rafforzerebbe, indebolirebbe o lascerebbe invariato ciascun candidato.
5. Pubblica la migliore spiegazione attuale e perché prevale, indicando lo stato provvisorio. Mantieni visibili le alternative e chiarisci se il risultato è una diagnosi, un'ipotesi di lavoro o un insieme irrisolto.
6. Pubblica la prossima azione di verifica e la modalità di errore rilevante, inclusi gli elementi che mostrerebbero che la spiegazione è errata o il collegamento probatorio inaffidabile.
7. Pubblica conclusione attuale, insieme dei candidati e condizione osservabile di revisione. Se nessun candidato ha sostegno discriminante o manca un'osservazione decisiva, sospendi il risultato invece di scegliere la narrazione più vivida.

## Public output contract

Restituisci `observation`, `candidate_explanations`, `comparison_criteria`, `discriminating_evidence`, `provisional_best_explanation`, `next_test` e `flip_condition`. La prima riga deve dire «migliore spiegazione attuale», o equivalente, quando il risultato è provvisorio. Gli elementi a sostegno hanno etichette **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; l'adeguatezza di un candidato è un'inferenza, non una prova diretta.

## Evidence and uncertainty rules

Un fatto sorprendente può motivare un'ipotesi ma non determinarne la causa. Richiedi sostegno indipendente o discriminante prima di rafforzare un candidato. Evita di contare più volte la stessa osservazione sotto criteri diversi. Se i candidati spiegano i fatti altrettanto bene, segnala la competizione irrisolta. Se una prova rilevante non è disponibile, mantieni la migliore spiegazione provvisoria o sospesa e indica le prove mancanti.

## Stop conditions

Fermati e fai una domanda bloccante quando l'osservazione o l'obiettivo decisionale è troppo vago per identificare spiegazioni candidate. Sospendi se è disponibile un solo candidato, non esistono implicazioni verificabili o mancano prove decisive. Fermati quando premesse esplicite implicano il risultato o il lavoro residuo riguarda qualità delle fonti, validità formale o confronto di opzioni.

## Complement handoff

Passa a `value-of-information` quando la decisione principale è acquistare, raccogliere o attendere informazioni discriminanti. Trasmetti candidati, prove che cambierebbero la decisione e costo o ritardo della prossima prova. Il complemento non deve ripetere il confronto delle spiegazioni.

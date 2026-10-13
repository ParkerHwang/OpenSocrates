## Purpose

Usa questa procedura quando il risultato di una decisione dipende dalla risposta di un altro attore, il cui risultato dipende a sua volta dalla decisione. Rende visibili giocatori, azioni disponibili, incentivi, informazioni, sequenza temporale e impegni credibili prima di raccomandare una mossa. Non autorizza a inventare una matrice dei guadagni, assegnare probabilità o chiamare un risultato equilibrio senza evidenze a supporto.

## Use when

Usala per mosse competitive, negoziazioni, offerte, prezzi, ingresso o deterrenza, contratti, standard condivisi e altre scelte cui un'altra parte può adattarsi strategicamente. È utile quando manca la risposta a «che cosa faranno se facciamo questo?» o quando una promessa, minaccia, reputazione o vantaggio informativo potrebbe cambiare il risultato. Interazioni ripetute e possibilità di cooperazione devono essere dichiarate, non assunte.

## Do not use when

Non usarla per ottimizzare la scelta di un solo attore quando l'ambiente non offre risposte strategiche significative. Non usarla per una regola vincolante senza discrezionalità, una scelta puramente meccanica o una situazione in cui il presunto avversario non può influire sul risultato. Non ridurre una relazione negoziale a una competizione a somma zero senza evidenze. Non dedurre razionalità, motivazioni nascoste o guadagni numerici solo perché un'azione sembra conveniente.

## Inputs to establish

Stabilisci decisione centrale, giocatori e diritti decisionali, ogni azione praticabile, risultato valorizzato da ciascuno, informazioni disponibili, ordine delle mosse e natura unica o ripetuta dell'interazione. Registra impegni credibili, vincoli e comportamenti precedenti soltanto se supportati da fonti o forniti. I guadagni possono restare ordinali o qualitativi quando manca una scala difendibile. Poni al massimo due domande concise, soltanto se un giocatore, un'azione, un incentivo, una condizione informativa o un fatto temporale mancante potrebbe cambiare la mossa raccomandata.

## Procedure

1. Pubblica decisione centrale e registro dei giocatori, indicando chi può agire, chi è interessato e chi può porre un veto o ritardare. Indica se i ruoli sono osservati, forniti dall'utente, inferiti o assunti; questo crea il perimetro visibile del gioco. Visible output/state change: perimetro del gioco pubblicato.
2. Pubblica azioni e informazioni di ciascun giocatore. Mostra azioni praticabili, ciò che ciascuno può osservare, mosse simultanee o sequenziali e ripetizione dell'interazione; questo trasforma una competizione vaga in una struttura specifica. Visible output/state change: struttura pubblicata.
3. Pubblica un registro degli incentivi per i risultati rilevanti. Usa conseguenze supportate da fonti o fornite dall'utente, etichettandole verified, computed, inferred, assumed, unverified o conflicted; conserva confronti ordinali quando guadagni esatti non sono difendibili. Visible output/state change: registro degli incentivi pubblicato.
4. Pubblica il controllo delle risposte: confronta migliori risposte credibili in un contesto simultaneo o ragiona a ritroso dalla decisione finale in uno sequenziale. Se un'azione dominante è supportata, spiega perché; altrimenti mostra coppie di risposte rilevanti senza fingere di conoscere ogni motivazione. Visible output/state change: controllo delle risposte pubblicato.
5. Pubblica risultati stabili candidati e indica se esiste uno, più di uno o nessun candidato supportato. Usa «equilibrio» soltanto quando le assunzioni su azioni, incentivi, informazioni e tempi hanno evidenze sufficienti; altrimenti definiscilo condizionale e indica ciò che manca. Visible output/state change: stato del risultato pubblicato.
6. Pubblica leve di intervento e mossa raccomandata. Spiega se la mossa cambia incentivi, informazioni, tempi, azioni disponibili o credibilità degli impegni e aggiungi un segnale di risposta osservabile; questo rende attuabile la strategia. Visible output/state change: mossa e segnale pubblicati.
7. Pubblica conclusione, incertezza principale e condizione osservabile che cambierebbe la mossa. Se manca un guadagno, un giocatore o un fatto temporale decisivo, pubblica un risultato sospeso e il minimo controllo per sbloccarlo, anziché scegliere un vincitore immaginario. Visible output/state change: stato di sospensione pubblicato.

## Public output contract

Restituisci un risultato compatto con `players`, `actions`, `incentives`, `information`, `timing`, `response_analysis`, `candidate_outcome`, `equilibrium_caveat`, `move` e `flip_condition`. Un risultato candidato non è automaticamente desiderabile, equo, efficiente o inevitabile. Indica se è supportato, condizionale, in conflitto o sospeso. I fondamenti usano le etichette delle evidenze della scheda; le alternative riassumono mosse o configurazioni degli impegni sostanzialmente diverse. Non esporre una trascrizione del ragionamento privato.

## Evidence and uncertainty rules

Separa comportamento osservato e teoria delle motivazioni. Un'affermazione sui guadagni richiede una fonte, un registro fornito dall'utente, un calcolo riproducibile o un'assunzione esplicita; etichetta fonte e ambito. Non inventare probabilità, tassi di sconto, informazioni nascoste o razionalità. Un andamento stabile delle risposte significa che nessun cambiamento unilaterale supportato migliora il risultato dichiarato sotto le assunzioni dichiarate; non prova desiderabilità sociale. Una minaccia o promessa conta soltanto se l'attore avrebbe ancora un motivo per attuarla al momento della decisione. Indica incentivi mancanti, discordanti o superati come unverified o conflicted e ridimensiona la conclusione di conseguenza.

## Stop conditions

Interrompi e poni una domanda bloccante quando due insiemi plausibili di giocatori, azioni o tempi portano a mosse sostanzialmente diverse e lo scopo dell'utente non permette di scegliere. Sospendi quando manca un incentivo, una condizione informativa o una sequenza decisiva. Interrompi senza instradare quando non esiste interdipendenza strategica significativa. Concludi quando struttura, risposta condizionale, mossa, stato delle evidenze e segnale di cambiamento sono pubblici; non proseguire i calcoli per creare falsa precisione.

## Complement handoff

Passa a `stakeholder-analysis` soltanto quando la struttura del gioco rivela questioni rilevanti di potere, consenso, legittimità, sostegno all'attuazione o gruppi interessati ma non rappresentati. Trasmetti registro dei giocatori, incentivi, conflitti, impegni e incertezza irrisolta. Il complemento deve mappare attori e necessità di coinvolgimento; non deve ripetere l'analisi delle risposte o fabbricare guadagni mancanti.

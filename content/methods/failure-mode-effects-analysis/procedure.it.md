## Purpose

Usa questa procedura per identificare come un processo, prodotto o controllo pianificato potrebbe fallire prima di farvi affidamento. Collega una modalità di guasto al suo effetto, alla causa plausibile, alla rilevazione esistente e al controllo preventivo o di rilevazione. Il risultato è una priorità ordinale e un elenco di azioni con responsabili, non un falso punteggio di rischio. Rende visibile l'incertezza e concentra l'impegno sui guasti le cui conseguenze o controlli deboli richiedono attenzione prioritaria.

## Use when

Usala per un lancio, una modifica al flusso di lavoro, un servizio, un passaggio di consegne, una barriera di sicurezza, una pipeline di dati o una funzionalità di prodotto con sequenza e punti di possibile guasto definiti. È utile prima dell'impegno, dopo una modifica progettuale rilevante o quando un incidente ricorrente rivela guasti non esaminati. Usa dati degli incidenti, test, registri di servizio e competenze disponibili. Delimita l'analisi al processo o componente che può essere descritto e su cui si può intervenire.

## Do not use when

Non usarla al posto di una risposta di emergenza, una revisione della conformità legale, un'analisi dei pericoli richiesta a uno specialista o una diagnosi causale di un incidente già ricorrente. Non assegnare numeri a gravità, frequenza o rilevabilità senza scala, calibrazione e fonte. Non confondere un lungo elenco con la completezza e non dare priorità a un guasto soltanto perché è più facile immaginarlo. Se il perimetro del processo o la funzione prevista è sconosciuto, stabiliscilo prima oppure sospendi la valutazione.

## Inputs to establish

Nomina processo, prodotto o componente, perimetro, funzione prevista, utenti, condizioni operative e controlli correnti. Mappa i principali passaggi o interfacce e identifica pericoli, vincoli, incidenti, risultati dei test e responsabili noti. Definisci il linguaggio ordinale prima di ordinare le priorità, per esempio urgente, rilevante, da monitorare o a bassa attenzione, spiegando ogni etichetta nel contesto. Poni al massimo due domande che potrebbero cambiare l'ordine, come «Quale guasto potrebbe causare un danno irreversibile?» o «Quale controllo lo rileverebbe prima del rilascio?».

## Procedure

1. **Stabilisci il perimetro dell'analisi.** Descrivi funzione prevista, contesto operativo, interfacce ed esclusioni; dividi un grande processo in una sequenza gestibile. **Visible output/state change:** pubblica perimetro e passaggi, indicando come unverified funzioni o condizioni sconosciute.
2. **Nomina modalità di guasto ed effetti.** Per ogni passaggio, indica che cosa potrebbe andare storto e l'effetto immediato, successivo, sull'utente o sulla sicurezza. Distingui le modalità abbastanza da poterle affrontare con controlli diversi. **Visible output/state change:** pubblica un registro dei guasti e degli effetti collegato a ogni passaggio.
3. **Traccia cause e controlli correnti.** Registra cause plausibili, controlli preventivi e di rilevazione ed evidenze che un controllo funzioni realmente. Separa guasti osservati e possibilità ipotetiche. **Visible output/state change:** aggiungi campi per cause e controlli con stati verified, inferred, assumed o unverified.
4. **Stabilisci la priorità ordinale.** Applica la regola qualitativa prestabilita usando conseguenze, esposizione plausibile e debolezza dei controlli. Se gli input quantitativi non sono difendibili, non calcolare un prodotto o un numero di priorità del rischio; spiega il confronto a parole. **Visible output/state change:** pubblica una breve lista ordinata con il motivo per cui ogni elemento è urgente, rilevante, da monitorare o a bassa attenzione.
5. **Assegna le azioni di controllo.** Preferisci la prevenzione che elimina una causa, poi la rilevazione prima del danno, poi il contenimento dell'impatto. Nomina responsabile, evento di attivazione, evidenza di completamento e incertezza residua. **Visible output/state change:** pubblica un piano di controllo collegato a ogni modalità prioritaria.
6. **Rivaluta dopo la modifica.** Indica quale osservazione o test mostrerebbe riduzione dell'esposizione o miglioramento della rilevazione e che cosa riaprirebbe la modalità. **Visible output/state change:** pubblica una valutazione della priorità supportata, provvisoria o sospesa e una condizione di cambiamento; non chiudere una modalità solo perché un'azione è pianificata.

## Public output contract

Restituisci perimetro, modalità di guasto, effetti, cause, controlli correnti, priorità ordinale, responsabile e segnale di verifica. Indica se ogni elemento rilevante è osservato, inferred, assumed, unverified o conflicted. Non presentare punteggi inventati di gravità/frequenza/rilevabilità né un ordine preciso senza provenienza. La Conclusion Card può riassumere il guasto che richiede più attenzione e la condizione che ne cambierebbe la priorità; la traccia può contenere il registro completo.

## Evidence and uncertainty rules

Un guasto ipotetico non è una frequenza osservata. Un controllo esistente non è efficace soltanto perché documentato; le evidenze devono mostrarne funzionamento, copertura o un test delimitato. Mantieni conseguenza, probabilità e rilevabilità come giudizi separati. Usa un linguaggio ordinale soltanto con definizione locale e base dichiarata. Se una soglia di sicurezza o normativa è vincolante, rimetti la decisione al requisito autorevole e indica le interpretazioni non verificate. Se due valutazioni credibili discordano, etichetta la priorità conflicted e sospendi l'ordine delle azioni dove il conflitto è rilevante.

## Stop conditions

Interrompi quando funzione prevista, perimetro o condizione operativa non possono essere stabiliti, quando un guasto con conseguenze gravi non ha alcun contenimento sicuro o quando l'ordine dipenderebbe da numeri inventati. Per pericoli immediati, segui prima il processo applicabile agli incidenti o alla sicurezza. Sospendi una raccomandazione di rilascio quando un controllo decisivo non è stato testato o non ha un responsabile assegnato.

## Complement handoff

Passa a premortem-analysis quando un piano scelto richiede, prima dell'impegno, un racconto di fallimento umano e segnali precoci. Trasmetti piano delimitato, modalità prioritarie di guasto, effetti e controlli; il complemento deve aggiungere scenari plausibili senza trasformare una priorità ordinale in falsa precisione.

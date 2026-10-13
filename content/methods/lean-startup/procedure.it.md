## Purpose

Usa questa procedura per ridurre l'incertezza di un'ipotesi di mercato, prodotto o modello di business attraverso un esperimento minimo di apprendimento. Trasforma il presupposto più rischioso in un test sicuro con una metrica utile per agire e una decisione dichiarata in anticipo. Un MVP è qui uno strumento di apprendimento, non un prodotto incompleto, un piano di lancio completo o una prova della domanda solo perché qualcosa è stato distribuito.

## Use when

Usala quando un'ipotesi importante su valore, crescita, adozione o ricavi non è verificata e una piccola osservazione potrebbe cambiare la scelta fra cambiare direzione, perseverare o fermarsi. È adatta a una decisione di prodotto o business con destinatario identificabile, esposizione delimitata e metrica osservabile. Usala prima di investimenti costosi, quando un test reversibile può rispondere alla domanda.

## Do not use when

Non eseguire un test minimo reale quando sicurezza, legge, privacy, protezione informatica o esposizione irreversibile di clienti o operazioni lo rendono inappropriato. Non chiamare esperimento un rilascio senza misurazione e non usare metriche di vanità come prove di apprendimento. Non usarla per attività puramente meccaniche, decisioni vincolanti senza discrezionalità sperimentale o problemi dovuti a cause operative sconosciute da diagnosticare prima.

## Inputs to establish

Stabilisci decisione, utente o contesto destinatario, un'ipotesi falsificabile, presupposto più rischioso e prove disponibili. Definisci test minimo o MVP, limite di esposizione, metrica utile per agire e sua unità, finestra di osservazione, soglia o regola qualitativa, responsabile e limite di arresto o ripristino. Registra effetti di selezione, limiti di accesso e fonti della situazione iniziale. Poni al massimo due domande concise solo se cambiano sicurezza del test, metrica o decisione successiva; altrimenti indica la lacuna come non verificata e sospendi se decisiva.

## Procedure

1. **Pubblica l'ipotesi.** Formula una proposizione condizionale che colleghi un'azione o offerta a un contesto destinatario e a un risultato osservabile. Etichetta ogni fondamento come verificato, calcolato, inferito, assunto o non verificato. **Risultato visibile/cambiamento di stato:** ipotesi falsificabile.
2. **Pubblica il presupposto più rischioso.** Seleziona quello il cui fallimento cambierebbe maggiormente la decisione e le cui prove sono più deboli o discordanti. Spiega perché conta e quali prove lo indebolirebbero; conserva l'incertezza senza inventare probabilità. **Risultato visibile/cambiamento di stato:** presupposto più rischioso.
3. **Pubblica la scheda del test minimo.** Progetta il più piccolo test reversibile con pubblico o ambito limitato, artefatto, durata, responsabile, limiti di consenso o accesso e condizione di arresto o ripristino. Se un test reale crea esposizione rilevante, sospendilo e indica una verifica più sicura senza esposizione reale. **Risultato visibile/cambiamento di stato:** scheda del test minimo o sospensione.
4. **Pubblica la specifica di misurazione.** Indica metrica utile per agire, unità, fonte, finestra di osservazione, riferimento iniziale se disponibile e soglia o regola decisionale. Spiega perché la metrica rappresenta la domanda di apprendimento; etichetta una soglia operativa come presupposto. **Risultato visibile/cambiamento di stato:** stato di misurazione verificabile.
5. **Pubblica il registro dei risultati.** Dopo un test autorizzato, registra comportamento atteso e osservato, osservazioni mancanti, effetti di selezione, deviazioni e stato delle prove. Non riempire un risultato assente con una storia di successo; senza risultati l'ipotesi resta non verificata. **Risultato visibile/cambiamento di stato:** registro dei risultati.
6. **Pubblica la decisione successiva.** Applica la regola dichiarata anticipatamente per scegliere cambiamento di direzione, perseveranza, arresto o sospensione. Indica ipotesi modificata o prossimo test, responsabile, limite e una o due condizioni osservabili che cambierebbero la scelta. **Risultato visibile/cambiamento di stato:** decisione delimitata.

## Public output contract

Restituisci campi pronti per la scheda chiamati `hypothesis`, `riskiest_assumption`, `minimum_test`, `metric_threshold` e `next_decision`. Il test deve indicare ambito sicuro, segnale osservabile e condizione di arresto o ripristino. La metrica deve identificarne fonte e unità; la decisione distingue cambiamento di direzione, perseveranza, arresto e sospensione. Includi al massimo due incertezze rilevanti nel risultato compattato. Una metrica, soglia o risultato decisivi mancanti producono un esito non verificato o sospeso, non una raccomandazione incondizionata.

## Evidence and uncertainty rules

Un artefatto distribuito non prova la domanda e una metrica non prova automaticamente un rapporto causale. Etichetta osservazioni dirette e fonti collegate come verificate solo se sostengono il fondamento specifico; mostra dati ed espressioni per risultati calcolati; indica ragionamenti modellistici come inferiti, soglie scelte o premesse non testate come assunte, verifiche mancanti come non verificate e disaccordi come contrastanti. Specifica contesto testato, limiti di accesso o selezione e finestra temporale. Non inventare probabilità, conversioni, dimensioni dei campioni o reazioni dei clienti. Un test minimo aggiorna l'ipotesi in quel contesto, non la generalizza a ogni utente o periodo futuro.

## Stop conditions

Sospendi quando decisione, contesto, presupposto più rischioso, metrica utile per agire o regola decisionale mancano e potrebbero cambiare l'esito. Ferma test con esposizione insicura, illegale, invasiva della privacy, sensibile alla sicurezza informatica, irreversibile o non autorizzata. Fermati se nessun segnale osservabile distingue le alternative, manca un ripristino necessario o si inferisce il risultato da una metrica di vanità. Per un guasto operativo con causa originaria sconosciuta, trasferisci il lavoro invece di mascherarlo con un esperimento di prodotto.

## Complement handoff

Passa a `jobs-to-be-done` quando il test non chiarisce il compito sottostante dell'utente, il contesto o il progresso desiderato e la scoperta deve precedere l'ipotesi di prodotto. Trasmetti solo contesto destinatario, ipotesi, presupposto più rischioso, stato delle prove osservate e bisogno irrisolto. Non ripetere l'esperimento e non suggerire che il passaggio fornisca risultati mancanti. Usa prima `assumption-mapping` quando più presupposti richiedono una priorità prima di testarne uno.

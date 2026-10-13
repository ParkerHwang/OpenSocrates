## Purpose

Usa questa procedura per svolgere un ciclo delimitato Plan–Do–Check–Act su un'ipotesi di miglioramento operativo. Rende visibili obiettivo, misura, piccolo ambito esecutivo, regola di confronto e decisione di standardizzazione, affinché il miglioramento accumuli prove e memoria organizzativa. È un ciclo controllato di apprendimento, non un sostituto della diagnosi di una causa originaria sconosciuta o della risposta a un incidente di sicurezza attivo.

## Use when

Usala quando un processo o servizio può cambiare in un ambito piccolo e reversibile, il miglioramento previsto è misurabile e cicli ripetuti possono elevare uno standard. Si adatta a un'ipotesi che richiede una breve finestra di osservazione e una chiara scelta fra standardizzare, rivedere o abbandonare. Serve a imparare dall'esecuzione senza impegnare l'intera operazione in un cambiamento non testato.

## Do not use when

Non usarla se la causa originaria è sconosciuta e la sperimentazione può nascondere o peggiorare danni, una regola vincolante non lascia discrezionalità o serve una risposta urgente a problemi di sicurezza, protezione informatica, legalità o incidenti. Non eseguire un ciclo solo per creare attività senza una regola di controllo. Non trasformare richieste meccaniche in programmi di miglioramento e non standardizzare una modifica perché annunciata o completata una volta.

## Inputs to establish

Stabilisci obiettivo, riferimento iniziale osservato o stato del processo, ipotesi, ambito, responsabile e direzione prevista del cambiamento. Prima di Do definisci metrica, unità, fonte, finestra di osservazione, limiti protettivi, condizione di arresto e regola di confronto. Specifica prove per standardizzare, rivedere o abbandonare, e dove registrare prossimo ciclo o standard versionato. Poni al massimo due domande concise solo se un'assenza può cambiare limite di sicurezza, misura o decisione Act; altrimenti etichetta la lacuna come non verificata e sospendi se decisiva.

## Procedure

1. **Pubblica la scheda Plan.** Indica obiettivo, riferimento iniziale, ipotesi di miglioramento, direzione prevista, ambito, responsabile e limite temporale. Etichetta il riferimento come verificato, calcolato, fornito dall'utente, inferito, assunto o non verificato. **Risultato visibile/cambiamento di stato:** stato del piano.
2. **Pubblica la specifica Check.** Indica metrica, unità, fonte, metodo di raccolta, finestra, regola di confronto, limiti protettivi e condizione di arresto. Dichiara anticipatamente le prove per standardizzare, rivedere o abbandonare. **Risultato visibile/cambiamento di stato:** regola di controllo.
3. **Pubblica il registro Do.** Esegui solo nel piccolo ambito approvato e registra modifica effettiva, deviazioni, esclusioni, incidenti e osservazioni. Mantieni un percorso di ripristino e non ampliare l'esposizione perché il primo segnale sembra favorevole. **Risultato visibile/cambiamento di stato:** registro esecutivo verificabile.
4. **Pubblica il risultato Check.** Confronta valori o descrizioni attesi e osservati mediante la regola anticipata. Identifica dati mancanti, fattori confondenti, limiti delle fonti e contraddizioni. **Risultato visibile/cambiamento di stato:** scarto dei risultati con stato delle prove.
5. **Pubblica la decisione Act.** Scegli standardizzazione, revisione, abbandono o sospensione secondo prove e limiti protettivi. Se il risultato è misto o manca la misura decisiva, mantieni provvisoria la modifica e registra la condizione irrisolta. **Risultato visibile/cambiamento di stato:** decisione Act o sospensione.
6. **Pubblica il prossimo ciclo.** Registra standard versionato o ipotesi rivista, responsabile, prossima osservazione e una o due condizioni osservabili che cambierebbero la scelta. Conserva apprendimento e aspetti non verificati. **Risultato visibile/cambiamento di stato:** piano del prossimo ciclo o risultato sospeso.

## Public output contract

Restituisci campi per la scheda chiamati `plan_objective_measure`, `do_scope`, `check_rule` e `act_standardize_decision`, con stato delle prove per ogni fondamento rilevante. `plan_objective_measure` include riferimento iniziale o sua assenza; `do_scope` mostra esposizione delimitata; `check_rule` mostra confronto e regola di arresto; `act_standardize_decision` distingue standardizzare, rivedere, abbandonare e sospendere. Includi un'ipotesi per il prossimo ciclo o una ragione chiara per non continuare. La mancanza della misura decisiva produce un risultato sospeso.

## Evidence and uncertainty rules

Distingui osservazione diretta, fonte collegata, calcolo riproducibile, registro fornito dall'utente, inferenza e premessa operativa adottata. Per `computed` mostra dati, espressione, unità e arrotondamento quando pertinente. Senza riferimento iniziale difendibile o con metodo di raccolta cambiato, indica il confronto come non verificato. Non inventare probabilità, dimensioni degli effetti, campioni o certezza causale. Un ciclo può sostenere apprendimento locale ma raramente dimostra uno standard permanente; osservazioni credibili discordanti mantengono Act contrastante o sospeso. Conserva deviazioni e segnali negativi invece di riportare solo miglioramenti.

## Stop conditions

Sospendi se obiettivo, riferimento, misura, regola di confronto, responsabile o ambito sicuro mancano e possono cambiare Act. Fermati immediatamente se il ciclo crea danni in corso, indebolisce controlli necessari, supera l'autorizzazione o perde un ripristino sicuro. Se la causa originaria è sconosciuta e il ciclo può mascherarla, passa a `root-cause-analysis`. Fermati dopo un controllo fallito o inconcludente senza ipotesi rivista o prossima osservazione sicura; non ripetere Do senza apprendimento.

## Complement handoff

Passa a `root-cause-analysis` se Check rivela guasti ripetuti, percorsi causali concorrenti o debolezze dei controlli da diagnosticare prima di altri cicli. Trasmetti piano, ambito Do delimitato, risultato Check, deviazioni, stati delle prove e domanda residua sui controlli. Non trasmettere accuse infondate né avviare un secondo metodo completo solo perché il primo ciclo è inconcludente.

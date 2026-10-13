## Purpose

Usa questa procedura per scegliere una modalità di risposta dalla forma osservata di una situazione. Distingue rapporti causa-effetto ripetibili da situazioni che richiedono analisi esperta, esperimenti sicuri, contenimento urgente o migliore inquadramento. Lo scopo non è decorare raccomandazioni con etichette di dominio, ma rendere visibili prove della classificazione, azione conseguente e segnale che potrebbe cambiarla.

## Use when

Usala quando la risposta proposta potrebbe non adattarsi alla situazione: per esempio applicare processi fissi a problemi adattivi, attendere analisi durante perturbazioni rapide o trattare problemi diversi come uno solo. Serve quando scegliere tra standardizzare, analizzare, sperimentare e agire è la decisione stessa. Può anche separare una situazione mista in parti che richiedono risposte diverse.

## Do not use when

Non usarla per compiti puramente meccanici, regole accertate senza discrezionalità significativa o richieste di calcoli noti o trascrizioni. Non forzare classificazioni se l'utente vuole etichette decorative anziché cambiare azione. Non considerare situazioni complesse automaticamente più importanti o quelle chiare automaticamente sicure: la classificazione descrive il rapporto decisionale, non la gravità delle conseguenze.

## Inputs to establish

Stabilisci domanda decisionale, confine della situazione, orizzonte temporale, schema osservato ed eventuali vincoli immediati di sicurezza o continuità. Raccogli osservazioni, esempi precedenti, competenze di dominio e fatti dell'utente, indicando ciò che è controllato, inferito, assunto o ancora non verificato. Fai al massimo due domande concise, soltanto se la risposta potrebbe cambiare modalità d'azione. Se manca l'osservazione decisiva, dichiara un confine provvisorio e procedi soltanto fino a una sospensione chiaramente indicata.

## Procedure

1. Pubblica in una frase domanda decisionale, ambito, orizzonte e vincolo immediato. Contrassegna ciascun elemento come fornito dall'utente o assunto; questo crea il quadro visibile. Risultato visibile/cambiamento di stato: quadro pubblicato.
2. Pubblica un registro di osservazioni causali separando rapporti ripetibili, rapporti dipendenti da esperti, retroazione emergente, perturbazione acuta e osservazioni ancora non interpretabili. Allega uno stato probatorio a ogni osservazione rilevante. Risultato visibile/cambiamento di stato: registro pubblicato.
3. Pubblica una classificazione provvisoria: chiaro, complicato, complesso, caotico o confuso, con due o tre osservazioni favorevoli. Se parti diverse hanno classificazioni diverse, separa la situazione e pubblica confini distinti anziché fare una media. Risultato visibile/cambiamento di stato: classificazione pubblicata.
4. Pubblica la modalità adatta: osservare–classificare–rispondere per schemi ripetibili, osservare–analizzare–rispondere per quelli dipendenti da esperti, sperimentare–osservare–rispondere per quelli adattivi, agire–osservare–rispondere per perturbazioni urgenti. Per la classificazione confusa pubblica il minimo compito di inquadramento o osservazione che la elimini. Risultato visibile/cambiamento di stato: modalità pubblicata.
5. Pubblica una prossima azione sicura e segnali di apprendimento o transizione. Indica ciò che sarà osservato, da chi e quando; il segnale deve essere osservabile, non una speranza generale di miglioramento. Risultato visibile/cambiamento di stato: registro dei segnali pubblicato.
6. Pubblica stato conclusivo, prove, una incertezza rilevante e condizione che invertirebbe classificazione o modalità. Non affermare certezza soltanto perché hai scelto un'etichetta. Risultato visibile/cambiamento di stato: conclusione pubblicata.
7. Se confine, osservazione o vincolo mancanti potrebbero cambiare modalità, pubblica risultato sospeso o provvisorio e domanda o controllo bloccante. Lo stato passa a sospensione, anziché colmare la lacuna con fatti inventati. Risultato visibile/cambiamento di stato: sospensione pubblicata.

## Public output contract

Restituisci un risultato compatto pronto per la scheda con `decision_question`, `domain`, `classification_evidence`, `action_mode`, `transition_signals`, `next_action` e `flip_condition`. Il dominio è una conclusione sostenuta da osservazioni visibili, non un distintivo. I fondamenti usano **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted** ove applicabile. Includi al massimo tre ipotesi rilevanti e due incertezze irrisolte. Se sospeso, indica che cosa manca e quale controllo elimina la sospensione.

## Evidence and uncertainty rules

Osservazioni dirette, fonti identificate, registri dell'utente e calcoli riproducibili sono prove soltanto di ciò che sostengono effettivamente. Un'etichetta normalmente è inferita dallo schema, non verificata perché una fonte usa la stessa parola. Non inventare probabilità di transizione, impatto o successo. Separa esistenza della retroazione e interpretazione del suo significato. Indica confini cambiati, classificazioni concorrenti o osservazioni obsolete come conflicted o unverified e indebolisci la conclusione se possono cambiare la prossima azione.

## Stop conditions

Fermati e fai una domanda bloccante quando due confini o osservazioni plausibili richiedono azioni materialmente diverse e scopo dell'utente o vincoli autorevoli non permettono di scegliere. Sospendi se rapporto decisivo, vincolo immediato o segnale di transizione non sono stabilibili. Termina quando sono pubblicati una modalità attuabile, un segnale osservabile e una condizione di revisione. Non attendere analisi esaustive nell'urgenza: registra il contenimento e rivedi la classificazione dopo nuove osservazioni.

## Complement handoff

Passa a `scenario-planning` soltanto quando la classificazione espone futuri esterni coerenti che richiedono preparazioni diverse. Trasmetti confine pubblicato, prove di classificazione, modalità, segnali e incertezza irrisolta. Non ripetere la classificazione completa né chiedere al complemento fatti mancanti che devono prima eliminare la sospensione di questa procedura.

## Purpose

Usa questa procedura quando poche risposte dell’utente possono modificare sostanzialmente la domanda, lo standard delle evidenze o la raccomandazione. Le domande fanno emergere assunti, significati, ragioni, alternative e implicazioni, mantenendo la responsabilità di fornire una risposta circoscritta. Sono un aiuto alla decisione, non un modo per evitare di rispondere o guidare l’utente verso una conclusione predeterminata.

## Use when

Usala quando l’affermazione, i termini, l’ambito, le evidenze o la conseguenza desiderata dall’utente non sono chiari e un breve chiarimento cambierebbe il percorso. È adatta a coaching, insegnamento, deliberazione, autovalutazione e definizione collaborativa dei problemi. Applicala a un giudizio solo quando le risposte mancanti sono davvero decisive; altrimenti dichiara un assunto ragionevole e procedi.

## Do not use when

Non usarla per un compito meccanico, una richiesta a cui si può rispondere in sicurezza con un assunto circoscritto o una situazione in cui domande ripetute ritarderebbero soltanto l’azione. Non chiedere ragionamenti privati, informazioni personali non necessarie alla decisione o un’intervista aperta. Non usare domande suggestive che presuppongano la risposta desiderata.

## Inputs to establish

Stabilisci l’affermazione o la decisione dell’utente, i termini da chiarire, l’ambito attuale, le evidenze disponibili, le alternative già considerate e la conseguenza che interessa all’utente. Seleziona non più di tre domande decisive. Per ciascuna, indica cosa cambierebbe la risposta: inquadramento, stato delle evidenze, ordine delle opzioni o stato di completamento. Definisci una soluzione alternativa sicura se l’utente non risponde.

## Procedure

1. Pubblica una riformulazione neutrale dell’affermazione o della decisione e del punto irrisolto. Ciò crea uno stato condiviso della domanda senza implicare accordo.
2. Pubblica fino a tre domande circoscritte, ciascuna con il suo effetto sulla decisione e un formato di risposta breve o un intervallo consentito. L’insieme visibile è l’unica richiesta di chiarimento; non aggiungere un questionario nascosto.
3. Registra ogni risposta come fornita dall’utente, non ricevuta o ambigua e pubblica l’effetto immediato su ambito, termini, evidenze o alternative. Questo rende visibile il cambiamento nello stato del giudizio.
4. Pubblica la ragione più forte a sostegno e un controesempio credibile o un’alternativa emersa dalle risposte. Distingui una risposta dalle evidenze sul mondo.
5. Pubblica una conclusione provvisoria o la prossima azione circoscritta, specificando cosa si può fare senza un’altra domanda. Se una risposta cambia il percorso, descrivi il nuovo percorso in termini semplici, senza nascondere il cambiamento.
6. Pubblica l’incertezza residua e la condizione osservabile che cambierebbe la conclusione. Tratta le domande senza risposta come assunti solo quando l’assunto è sicuro e reversibile.
7. Pubblica la risposta attuale, perché deriva dalle informazioni ricevute e se il compito è completo, provvisorio o sospeso. Se la domanda decisiva resta senza risposta, non inventare certezza.

## Public output contract

Restituisci `no_more_than_three_decisive_questions`, `decisive_questions` (massimo tre), `why_each_matters`, `answers_and_status`, `decision_effects`, `provisional_conclusion`, `remaining_uncertainty`, `next_action` e `flip_condition`. Le domande devono essere visibili e circoscritte; la scheda finale non deve esporre una trascrizione della deliberazione privata. Nella scheda trovano posto al massimo due incertezze irrisolte. Le ragioni riportano le etichette di stato **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**.

## Evidence and uncertainty rules

Le risposte dell’utente stabiliscono preferenze, ambito o contesto, salvo che forniscano anche evidenze verificabili. Non promuovere una risposta a **verified** senza una fonte identificabile a sostegno. Una domanda decisiva senza risposta lascia l’affermazione interessata **assumed**, **unverified** o **held**, secondo la sua rilevanza. Se le risposte sono in conflitto, mostra il conflitto e non aggiungere domande, a meno che una sola domanda breve possa risolverlo in sicurezza.

## Stop conditions

Fermati e poni le domande selezionate quando procedere senza di esse cambierebbe sostanzialmente l’azione. Non porne più di tre; se l’utente non può rispondere, continua con un assunto reversibile oppure sospendi il giudizio. Smetti di fare domande quando percorso e conclusione sono abbastanza stabili per agire, o quando il compito è meccanico e non resta alcun giudizio da formulare.

## Complement handoff

Passa ad `assumption-mapping` solo quando le risposte rivelano diversi assunti rilevanti da prioritizzare e verificare. Trasmetti l’insieme delle domande con e senza risposta, lo stato degli assunti e l’attuale condizione di cambiamento. Il complemento non deve ripetere le domande socratiche né trasformarle in un’intervista senza limiti.

## Purpose

Usa questa procedura per determinare se una conclusione segue necessariamente da premesse esplicite e una regola, separando validità e verità delle premesse. Standardizza l'argomentazione, espone premesse nascoste, controlla la forma e identifica la premessa la cui falsità invaliderebbe la conclusione. Una forma valida non rende da sola solida un'argomentazione sul mondo reale.

## Use when

Usala per applicazione di regole, controllo di argomentazioni formali, interpretazione contrattuale o normativa e affermazioni secondo cui un risultato deve seguire da condizioni dichiarate. È adatta quando le premesse pertinenti possono essere esplicitate e la domanda riguarda implicazione necessaria, non generalizzazione empirica.

## Do not use when

Non usarla quando le premesse sono incerte e il compito effettivo è stimare, diagnosticare, generalizzare o aggiornare fiducia. Non trattare premesse probabili come dimostrate, confondere `P(E|H)` con implicazione necessaria o chiamare valida una forma invalida perché la conclusione risulta vera. Non inventare regole non fornite dall'utente o dalla fonte governante.

## Inputs to establish

Stabilisci conclusione proposta, premesse, regola o implicazione governante, ambito, definizioni e fonte di ogni premessa. Marca esplicitamente le premesse nascoste e identifica se occorre validità, solidità o soltanto risultato condizionale. Fai al massimo una domanda decisiva quando regola o premessa mancante cambia la forma; altrimenti dichiara l'ipotesi condizionale.

## Procedure

1. Pubblica la conclusione e standardizza l'argomentazione in premesse numerate, regola e conclusione. Contrassegna le premesse nascoste come `[implicit]`; questo crea lo stato visibile della formalizzazione.
2. Pubblica la forma: per esempio modus ponens, modus tollens, sillogismo valido, affermazione del conseguente o negazione dell'antecedente. Se nessuna forma riconosciuta corrisponde, mostra il rapporto strutturale pertinente senza forzare etichette.
3. Pubblica il giudizio di validità: assumendo vere le premesse, la conclusione deve essere vera? Indica lo schema del controesempio se la forma è invalida.
4. Pubblica una tabella dello stato delle premesse con fonte, ambito e stato probatorio di ogni premessa e regola. Separa forma valida e argomentazione solida; questo aggiorna visibilmente il giudizio.
5. Pubblica la premessa invalidante o la condizione della regola. Indica esattamente ciò che romperebbe l'implicazione e distingui eccezioni alla regola da premesse false.
6. Pubblica la conclusione come solida, valida ma non solida, invalida o condizionale, con il minimo controllo mancante. Non rafforzarne lo stato perché plausibile.
7. Pubblica conclusione attuale e condizione osservabile di revisione. Se manca una premessa o regola decisiva, sospendi l'affermazione sul mondo reale preservando l'implicazione condizionale.

## Public output contract

Restituisci `premises`, `hidden_premises`, `rule`, `rule_or_form`, `conclusion`, `validity_verdict`, `premise_status`, `invalidating_premise`, `soundness_verdict` e `flip_condition`. Il risultato deve specificare se la forma è valida e se le premesse sono sostenute, senza fonderle in un'unica etichetta di fiducia. I fondamenti usano **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**.

## Evidence and uncertainty rules

La validità è un rapporto strutturale e non verifica premesse. Una fonte può sostenere una premessa senza dimostrare che la regola si applichi a questo ambito. Le premesse nascoste restano ipotesi finché sostenute. Se una premessa è controversa, preserva il risultato condizionale e indebolisci o sospendi la conclusione applicata. Non usare una sola conclusione vera per convalidare inferenze invalide.

## Stop conditions

Fermati e fai una domanda bloccante se manca regola governante o conclusione e forme possibili portano a risultati diversi. Sospendi quando una premessa rilevante non è controllabile, riportando comunque il condizionale valido se esiste. Fermati se il compito è probabilistico, causale o comparativo, anziché di implicazione necessaria.

## Complement handoff

Passa a `conceptual-analysis` quando la disputa formale dipende da termine ambiguo o definizione dell'ambito. Trasmetti premesse standardizzate, termine controverso e regola interessata. Il complemento deve chiarire il concetto senza rifare il giudizio di validità.

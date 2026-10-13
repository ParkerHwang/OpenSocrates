## Purpose

Usa questa procedura per conclusioni che normalmente seguono, ma sono ritirabili quando emergono eccezioni o nuove prove. Dichiara una regola di norma, la applica provvisoriamente, distingue elementi contrari alla conclusione da quelli che ne indeboliscono il collegamento e registra condizioni esplicite di ritiro. Produce un giudizio provvisorio controllato, non un modo indebolito di formulare regole incondizionate.

## Use when

Usala in diritto, politiche, medicina, operazioni, regole di buon senso e altri ambiti dove generalizzazioni ammettono eccezioni o prove arrivano nel tempo. È adatta a ragionamenti «normalmente», «salvo» e «prima facie» e giudizi che devono restare rivedibili senza diventare arbitrari.

## Do not use when

Non usarla se regole rigorose e premesse accertate implicano il risultato, o il problema è soltanto graduatoria delle fonti o aggiornamento statistico. Non elencare tutte le eccezioni immaginabili, trattare problemi di credibilità come contraddizioni dirette o preferire enunciati recenti soltanto perché recenti. L'assenza di elementi contrari noti non dimostra la conclusione.

## Inputs to establish

Stabilisci regola di norma, fatti attivanti, ambito, eccezioni note, possibili elementi contrari o invalidanti il collegamento e decisione interessata. Identifica regole più specifiche che potrebbero prevalere. Fai al massimo due domande decisive se regola o fatto attivante sono poco chiari; altrimenti indica la premessa come provvisoria.

## Procedure

1. Pubblica la regola di norma in forma delimitata, come «normalmente P implica Q», con fonte, ambito e stato probatorio. Questo crea lo stato visibile della regola.
2. Pubblica fatti applicabili e conclusione prima facie. Etichettala come provvisoria e indica le condizioni d'applicazione della regola.
3. Pubblica separatamente elementi contrari che sostengono non-Q ed elementi che indeboliscono il collegamento P-Q. Registra ciascuno come controllato, asserito o sconosciuto.
4. Pubblica regole concorrenti e applica specificità quando una è un vero sottoinsieme dell'altra. Se non risolve il conflitto, indica stato conflittuale o sospeso anziché affidarti a recenza o tono di certezza.
5. Pubblica condizioni esplicite di ritiro: fatto osservabile che ritirerebbe Q, indebolirebbe la giustificazione o richiederebbe nuovo giudizio. La condizione deve essere più precisa di «appaiono nuove informazioni».
6. Pubblica lo stato aggiornato dopo gli elementi contrari noti: provvisorio, sostenuto, ritirato, conflittuale o sospeso. Indica se la conclusione è cambiata per confutazione diretta, indebolimento del collegamento o conflitto irrisolto.
7. Pubblica conclusione attuale, elementi contrari applicabili e condizione di revisione. Se manca un fatto attivante o un'eccezione decisiva, sospendi o mantieni provvisorio il risultato anziché rafforzarlo a certezza.

## Public output contract

Restituisci `default_rule`, `applicable_facts`, `prima_facie_conclusion`, `exceptions_defeaters`, `rebutting_defeaters`, `undercutting_defeaters`, `specificity_resolution`, `withdrawal_conditions`, `current_status` e `flip_condition`. La scheda deve rendere visibili provvisorietà ed elementi contrari rilevanti. I fondamenti usano **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; non chiamare mai incondizionata la conclusione di norma.

## Evidence and uncertainty rules

Un elemento confutante confligge con la conclusione; uno che indebolisce il collegamento riduce la ragione per cui i fatti la sostengono, senza dimostrare l'opposto. La specificità è priorità strutturale, non regola di recenza. Controlla ambito e indipendenza delle nuove prove prima di cambiare stato. Se un elemento contrario rilevante resta irrisolto, indebolisci o sospendi il risultato e indica il controllo necessario.

## Stop conditions

Fermati e fai una domanda bloccante quando regola di norma o fatti attivanti non sono identificabili e regole concorrenti comportano azioni diverse. Sospendi se manca eccezione, fonte o condizione d'applicabilità decisiva. Fermati se la regola è rigorosa e senza eccezioni o il compito residuo è aggiornamento probabilistico.

## Complement handoff

Passa a `premortem-analysis` quando la regola provvisoria sostiene un piano scelto e resta da capire come potrebbe fallire. Trasmetti conclusione di norma, elementi contrari noti e condizioni di ritiro. Il complemento non deve riclassificare gli elementi contrari o ripetere l'inventario delle regole.

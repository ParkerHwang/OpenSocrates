## Purpose

Usa questa procedura per generalizzare a partire dalle osservazioni, mantenendo la conclusione probabilistica e delimitata dal campione. Identifica il tipo di induzione, controlla dimensione, diversità e rappresentatività del campione, cerca attivamente controesempi e dichiara ambito e forza della generalizzazione. Le osservazioni ripetute aumentano il supporto soltanto quando il campionamento e la base di misurazione giustificano l'estensione.

## Use when

Usala per andamenti nei dati, sondaggi, riscontri degli utenti, incidenti ripetuti e affermazioni che passano da casi osservati a una popolazione più ampia o a comportamenti futuri. È adatta a generalizzazioni statistiche, enumerative, causali o analogiche quando l'utente deve sapere fino a che punto le osservazioni supportano l'affermazione.

## Do not use when

Non usarla per un campione di convenienza non rappresentativo, per applicare una regola rigorosa o per un'affermazione causale che richiede un disegno causale anziché l'estensione di un andamento. Non trattare molte osservazioni duplicate come diversità, non dedurre «tutti» da un piccolo campione e non trasformare una tendenza plausibile in una conclusione necessaria.

## Inputs to establish

Stabilisci osservazioni, popolazione di riferimento o ambito futuro, processo di campionamento, definizione della misura, gruppi di confronto, finestra temporale e decisione interessata. Identifica il tipo di induzione e le distorsioni note di selezione, sopravvivenza, mancata risposta o misurazione. Poni al massimo una domanda decisiva quando la popolazione o la base del campione è sconosciuta e cambia l'ambito.

## Procedure

1. Pubblica le premesse osservate e la generalizzazione proposta come enunciati separati. Indica provenienza e stato delle evidenze di ogni osservazione; questo crea la base visibile dell'induzione.
2. Pubblica il tipo di induzione — enumerativa, statistica, causale o analogica — e il collegamento dal campione all'ambito di riferimento. Dichiara quali assunzioni rendono plausibile il collegamento.
3. Pubblica la base del campione: dimensione, diversità, selezione, casi mancanti, qualità della misurazione e copertura temporale. Distingui una descrizione supportata da fonti da un'affermazione inferita sulla rappresentatività.
4. Pubblica la ricerca del controesempio più forte e il suo risultato. Includi, quando disponibili, casi non selezionati, risultati negativi, differenze fra sottogruppi e plausibili eccezioni future.
5. Pubblica la generalizzazione delimitata con un limite di ambito e un'etichetta qualitativa di forza, come forte, moderata o debole. Sostituisci formulazioni universali con un intervallo di popolazione o proporzione soltanto quando quell'intervallo ha una provenienza difendibile.
6. Pubblica la conseguenza decisionale e la prossima osservazione che migliorerebbe o metterebbe maggiormente in discussione la generalizzazione. Indica se il risultato supporta un'azione, il monitoraggio o un ulteriore campionamento.
7. Pubblica la conclusione corrente e una condizione osservabile che cambierebbe il giudizio. Se il campione è troppo distorto, scarso o non pertinente al riferimento, sospendi o mantieni provvisorio il risultato anziché estrapolare.

## Public output contract

Restituisci `observations`, `induction_type`, `sample_basis`, `generalization`, `scope_limit`, `counterexample_risk`, `counterexample_search`, `strength`, `decision_consequence` e `flip_condition`. Il risultato deve distinguere i casi osservati dall'affermazione più ampia. I fondamenti usano le etichette **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; la generalizzazione è normalmente inferita, non verificata direttamente.

## Evidence and uncertainty rules

La sola dimensione del campione non ne stabilisce la rappresentatività. Controlla selezione, copertura, abbandoni, misurazione, equilibrio dei sottogruppi e pertinenza temporale. Un controesempio può limitare un'affermazione universale senza dimostrare la tendenza opposta. Non riutilizzare la stessa osservazione sia come supporto indipendente sia come test di un controesempio. Se manca la base del campione o l'ambito di riferimento, riduci o sospendi la conclusione.

## Stop conditions

Interrompi e poni una domanda bloccante quando non è possibile conoscere la popolazione di riferimento o il processo di campionamento e ambiti diversi cambierebbero l'azione. Sospendi quando il campione è sostanzialmente non rappresentativo, l'affermazione causale supera ciò che il disegno consente o resta irrisolto un rischio decisivo di controesempi. Interrompi quando il compito riguarda una regola rigorosa, una diagnosi fra ipotesi concorrenti o un confronto della qualità delle fonti.

## Complement handoff

Passa a `evidence-hierarchy` quando la domanda restante riguarda il peso che il campione o il disegno dello studio merita per l'affermazione. Trasmetti base del campione, generalizzazione, limite di ambito e principale rischio di controesempi. Il complemento non deve ripetere la procedura di generalizzazione.

## Purpose

Usa questa procedura per verificare se una classificazione o scomposizione è mutuamente esclusiva e collettivamente esaustiva allo stesso livello. Fissa un solo asse di classificazione, verifica separatamente sovrapposizioni e lacune e mantieni coerente la granularità delle categorie. Il risultato è una regola di classificazione difendibile con casi di confine noti, non la promessa che ogni categoria del mondo reale abbia confini naturalmente netti.

## Use when

Usala quando categorie, gruppi di responsabilità, opzioni, requisiti, cause o rami di un albero duplicano o omettono casi rilevanti. Serve a rivedere una classificazione esistente e come verifica mirata all'interno di un albero logico o struttura esecutiva. Usala quando il collo di bottiglia decisionale è la regola di classificazione, anziché una fonte fattuale.

## Do not use when

Non usarla se la sovrapposizione naturale è il fenomeno studiato, le categorie rappresentano intenzionalmente assi diversi o va semplicemente applicata una tassonomia vincolante. Non mescolare età, geografia, intenzione e fase di processo a uno stesso livello. Non nascondere una grande classe mancante sotto «altro» e non imporre una falsa esclusività quando l'appartenenza è realmente multietichetta.

## Inputs to establish

Stabilisci universo classificato, scopo decisionale, categorie candidate, singolo asse proposto, regola di inclusione, regola di esclusione e casi di confine noti. Indica se le categorie ammettono una sola etichetta o più etichette. Poni al massimo una domanda se universo o scopo sono sostanzialmente ambigui; altrimenti indica un universo delimitato.

## Procedure

1. Pubblica universo, scopo decisionale e unico asse di classificazione in una frase. Questo fissa lo stato visibile della classificazione e impedisce criteri mescolati.
2. Pubblica le categorie candidate con una regola di inclusione e una di esclusione per ciascuna. Etichetta i confini delle categorie come espliciti, inferiti o non verificati.
3. Pubblica il test di esclusività reciproca con casi plausibili che potrebbero appartenere a due categorie. Per ogni sovrapposizione unisci, ridefinisci i confini o ammetti esplicitamente più etichette, registrando il cambiamento di stato.
4. Pubblica il test di copertura collettiva usando casi limite e osservazioni note. Aggiungi una categoria solo se il caso mancante è pertinente all'universo dichiarato; altrimenti restringi l'universo e dichiara l'esclusione.
5. Pubblica un controllo di granularità del livello: confronta astrazione, dimensioni e uso decisionale delle categorie. Rielabora una categoria che sia una sottocategoria nascosta delle altre o troppo ampia per sostenere un'azione.
6. Pubblica casi di confine, regola finale ed eventuali sovrapposizioni lasciate intenzionalmente irrisolte. Non usare un contenitore vago «altro» per una quota rilevante dell'universo.
7. Pubblica risultato classificato, verdetto su sovrapposizioni e lacune e condizione osservabile che cambierebbe la conclusione. Se l'asse non sostiene la decisione o un caso importante non è classificabile, sospendi invece di forzare un'etichetta.

## Public output contract

Restituisci `classification_universe`, `classification_rule`, `classification_axis`, `categories`, `inclusion_rules`, `exclusion_rules`, `overlap_gap_check`, `overlap_check`, `coverage_check`, `granularity_check`, `boundary_cases` e `flip_condition`. Il risultato pubblico deve distinguere ME da CE e indicare se la classificazione è monoetichetta o multietichetta. I fondamenti usano **verificato**, **calcolato**, **inferito**, **assunto**, **non verificato** o **contrastante**; le categorie non sono prove della loro frequenza.

## Evidence and uncertainty rules

ME e CE sono controlli logici di copertura, non prove empiriche dell'utilità delle categorie. Un esempio può rivelare una sovrapposizione o lacuna senza stabilirne la frequenza. Tieni separate le osservazioni sostenute da fonti dalle scelte di progettazione delle categorie. Se manca una categoria rilevante, un caso controverso resta irrisolto o l'asse cambia la decisione, etichetta il risultato come provvisorio o sospeso.

## Stop conditions

Fermati e poni una domanda bloccante se universo o scopo della classificazione non sono delimitabili. Sospendi quando l'asse non rappresenta i casi rilevanti senza sovrapposizioni fuorvianti o una categoria mancante cambia la decisione. Fermati quando la regola supera ME/CE nell'ambito richiesto e il lavoro restante riguarda scomposizione strutturale o confronto di opzioni.

## Complement handoff

Passa a `logic-tree` quando le categorie validate sono il primo livello di una diagnosi o piano più ampio e richiedono rami ricorsivi e test alle foglie. Trasmetti universo, asse, categorie finali, casi di confine e verdetto di copertura. Il complemento non deve ripetere i controlli MECE allo stesso livello.

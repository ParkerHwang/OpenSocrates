## Purpose

Usa questa procedura per controllare se una regola, un costo, un flusso di lavoro o un'architettura familiare è realmente necessario o soltanto ereditato. Scomponi il problema in affermazioni e vincoli, verifica ciascuno e ricostruisci un'opzione a partire dai vincoli che resistono. La procedura protegge sia dall'imitazione acritica sia dalla riduzione avventata: un vincolo non viene scartato perché scomodo, e una possibilità fisica non è automaticamente un piano praticabile.

## Use when

Usala quando «si è sempre fatto così», una convenzione di settore, una dipendenza storica o una struttura di costi assunta blocca una riprogettazione di grande impatto. È adatta a prezzi, architetture di prodotto, processi operativi, allocazione delle risorse e requisiti quando l'utente vuole mettere in discussione la base di una scelta esistente. È utile quando un insieme di opzioni ormai superato sembra ereditare assunzioni non più valide.

## Do not use when

Non usarla per una procedura standard convalidata che il compito chiede soltanto di eseguire, o quando una regola vincolante, un vincolo di sicurezza, un obbligo legale o un'interfaccia fissata esternamente non può essere scartato. Non trattare preferenze, budget, tempi o coordinamento sociale come fatti puramente fisici. Non promettere una riprogettazione basata su assunzioni non verificate e non omettere i vincoli di attuazione dopo la scomposizione.

## Inputs to establish

Stabilisci risultato desiderato, approccio corrente, requisiti dichiarati, vincoli, risorse, dipendenze e motivo per cui l'approccio corrente è ritenuto necessario. Separa vincoli inderogabili, vincoli negoziabili, convenzioni e aspetti sconosciuti. Poni al massimo due domande decisive, soltanto quando la risposta modifica la ricostruzione. Identifica ogni regola ad alto impatto che deve restare in vigore.

## Procedure

1. Pubblica risultato desiderato e approccio corrente in una frase, poi indica perimetro e misura di successo. Questo crea una base visibile da confrontare con un'opzione ricostruita.
2. Pubblica una scomposizione dell'approccio in requisiti elementari, dipendenze e vincoli dichiarati. Indica se ogni elemento è fornito dall'utente, supportato da fonti, inferito o assunto; questo cambia lo stato da «dato» a «da verificare».
3. Pubblica un giudizio di necessità per ogni vincolo: fisicamente o logicamente necessario, vincolante per imposizione esterna, contingente, basato su preferenze o non verificato. Allega il test o la fonte che supporta il giudizio.
4. Pubblica l'insieme dei vincoli rimasti ed elimina soltanto le assunzioni che non hanno superato la verifica. Se un elemento controverso potrebbe incidere in modo rilevante su sicurezza, legalità o fattibilità, mantienilo come vincolo esplicito irrisolto anziché eliminarlo silenziosamente.
5. Pubblica una ricostruzione basata sui vincoli rimasti. Indica le implicazioni di risorse, tempo, dipendenze e coordinamento, così che la riprogettazione non sia soltanto fisicamente immaginabile.
6. Pubblica la differenza rispetto all'approccio convenzionale: che cosa cambia, quale assunzione lo consente e quale nuovo rischio o compromesso compare. Aggiungi una piccola azione di convalida per ogni requisito non verificato.
7. Pubblica requisiti derivati, opzione ricostruita e una condizione osservabile che cambierebbe il giudizio. Se manca un vincolo irriducibile o un input decisivo, usa una conclusione provvisoria o sospesa anziché dichiarare una svolta.

## Public output contract

Restituisci `irreducible_constraints`, `derived_requirements`, `reconstructed_option`, `assumptions_reintroduced`, `reintroduced_assumptions`, `conventional_delta`, `new_risks` e `flip_condition`. La prima riga indica se la riprogettazione è supported, provisional o held. Distingui un'opzione fisicamente possibile da una che soddisfa i requisiti dell'utente su costi, tempi, sicurezza e governance. I fondamenti della scheda usano le etichette **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; non presentare una convenzione senza etichetta come evidenza.

## Evidence and uncertainty rules

«Necessario» richiede una base logica, fisica, contrattuale, di sicurezza o un'altra base nominata; la scomodità non prova la necessità. Una fonte che descrive una pratica comune ne supporta la diffusione, non l'inevitabilità. I calcoli devono dichiarare input e unità. Se una ricostruzione dipende da una dipendenza non verificata, la conclusione può essere un'ipotesi delimitata, ma non una raccomandazione fortemente supportata. Conserva i conflitti anziché fare una media fra vincoli incompatibili.

## Stop conditions

Interrompi e poni una domanda bloccante quando il risultato desiderato o il confine inderogabile di sicurezza o legalità è poco chiaro e risposte diverse producono ricostruzioni diverse. Sospendi il risultato quando non può essere stabilito un vincolo irriducibile o un input richiesto. Interrompi il metodo quando ogni vincolo rilevante è fissato esternamente o il lavoro restante consiste in confronto ordinario di opzioni, verifica delle evidenze o attuazione.

## Complement handoff

Passa a `morphological-analysis` quando i requisiti rimasti possono variare lungo più dimensioni coerenti e il compito successivo è esplorare combinazioni. Trasmetti requisiti derivati, vincoli conservati ed esclusioni di fattibilità. Il complemento non deve ripetere la scomposizione né riaprire la disputa su quali assunzioni sono state eliminate.

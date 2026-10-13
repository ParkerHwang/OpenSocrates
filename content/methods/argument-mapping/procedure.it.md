## Purpose

Usa questa procedura per mostrare come affermazioni, fondamenti, obiezioni e confutazioni sostengono o indeboliscono una conclusione. Crea una mappa argomentativa verificabile, anziché una mappa mentale libera, mantenendo visibili premesse condivise, collegamenti privi di sostegno e obiezioni irrisolte. Può chiarire una controversia prima di decidere, ma disporre ordinatamente una premessa non la rende vera.

## Use when

Usala quando un'argomentazione politica, giuridica, strategica, di ricerca o di prodotto contiene diverse affermazioni annidate e non è chiaro quali prove sostengano quale conclusione. È adatta a controversie con più obiezioni, confutazioni o ipotesi condivise. Usala quando il compito principale è distinguere rapporti di sostegno e contestazione, poi indicare la forza risultante o la condizione di sospensione.

## Do not use when

Non usarla per un semplice elenco, un calcolo diretto o un compito riguardante soltanto la qualità delle fonti. Non rappresentare associazione, cronologia o somiglianza tematica come sostegno logico. Non dedurre la solidità di una conclusione dalla completezza della mappa e non nascondere scelte di valore in premesse apparentemente neutrali.

## Inputs to establish

Stabilisci conclusione bersaglio, decisione o domanda, ambito pertinente, fondamenti diretti, premesse condivise, obiezioni, confutazioni e fonti disponibili. Identifica ciascun elemento come fatto, regola, inferenza, preferenza o ipotesi. Fai al massimo due domande decisive quando un'affermazione o un ambito mancante cambierebbe la mappa; altrimenti segnala la lacuna e procedi.

## Procedure

1. Pubblica la conclusione principale e la decisione che deve sostenere. Indica lo stato attuale come sostenuto, provvisorio, conflittuale o sospeso: questo crea lo stato visibile dell'argomentazione.
2. Pubblica le premesse direttamente favorevoli e distingui quelle necessarie congiuntamente. Traccia soltanto collegamenti espliciti di sostegno e contrassegna ciascuno come dichiarato, inferito o non verificato.
3. Pubblica i sottofondamenti di ciascuna premessa, preservando la gerarchia tra affermazioni e fondamenti. Allega riferimenti a fonti o calcoli disponibili e registra i collegamenti non sostenuti come lacune.
4. Pubblica le obiezioni come rami separati di contestazione; pubblica confutazioni soltanto se rispondono all'affermazione effettiva dell'obiezione. Segnala come irrisolta un'obiezione quando la confutazione non cambia né le sue prove né il suo ambito.
5. Pubblica premesse nascoste o condivise e verifica se rimuoverle cambia la conclusione. Questa variazione identifica la più piccola debolezza rilevante, anziché attribuire uguale peso a ogni frase.
6. Pubblica un giudizio sulla mappa: collegamento sostenuto più forte, collegamento più debole, obiezione irrisolta ed eventuali rami ridondanti o irrilevanti. Distingui completezza della mappa, verità delle premesse e validità dell'inferenza.
7. Pubblica lo stato probatorio attuale della conclusione e una condizione osservabile di revisione. Se manca una premessa rilevante o resta un'obiezione decisiva irrisolta, indebolisci o sospendi la conclusione invece di correggere tacitamente l'argomentazione.

## Public output contract

Restituisci `claim_ground_objection_map`, `top_level_conclusion`, `direct_grounds`, `shared_premises`, `subgrounds`, `objections`, `rebuttals`, `unsupported_links`, `map_verdict` e `flip_condition`. Il risultato pubblico deve mostrare una mappa compatta di affermazioni, fondamenti e obiezioni, non una trascrizione del ragionamento privato. I fondamenti hanno etichette **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**. Includi nella scheda soltanto i rami rilevanti e trasferisci i dettagli alla traccia quando serve.

## Evidence and uncertainty rules

Una fonte può sostenere un'affermazione senza sostenere il collegamento tra essa e la conclusione. Valuta separatamente immediatezza, pertinenza e ambito. Le premesse condivise non vanno contate due volte come sostegni indipendenti. Una confutazione contro un testimone o una misura può indebolire il collegamento probatorio senza dimostrare la conclusione opposta. Fondamenti credibili in conflitto richiedono conflitto visibile e risultato sospeso o indebolito, salvo una regola di precedenza dichiarata che lo risolva.

## Stop conditions

Fermati e fai una domanda bloccante quando manca la conclusione bersaglio o l'ambito decisionale e interpretazioni concorrenti produrrebbero mappe diverse. Sospendi quando una premessa rilevante non può essere sostenuta o un'obiezione decisiva non è risolta. Fermati se il compito riguarda soltanto graduatoria delle fonti, calcolo semplice o definizione stabile; passa al metodo più specifico.

## Complement handoff

Passa a `evidence-hierarchy` quando la mappa mostra che il collo di bottiglia residuo è qualità delle fonti, disegno dello studio o immediatezza, anziché struttura argomentativa. Trasmetti soltanto collegamenti tra affermazioni e fonti, collegamenti privi di sostegno e conflitto rilevante. Il complemento non deve ricostruire l'intera mappa.

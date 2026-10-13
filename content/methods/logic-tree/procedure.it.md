## Purpose

Usa questa procedura per scomporre una domanda ampia di diagnosi, pianificazione o copertura in una gerarchia con rami reciprocamente chiari, complessivamente adeguati e traducibili in azioni alle foglie. Seleziona un solo asse di scomposizione per livello, separa alberi del perché e del come e associa una verifica o prossima azione a ogni ramo terminale. L'albero struttura la ricerca; non dimostra che ogni ramo sia vero.

## Use when

Usala quando il problema è ampio, le cause sono poco chiare, un piano richiede copertura o una domanda «perché», «come» o «cosa» necessita di una struttura esaustiva. È adatta a diagnosi, copertura dei rischi, requisiti ed esplorazione di soluzioni, quando rami sovrapposti causerebbero responsabilità duplicate o lavoro omesso.

## Do not use when

Non usarla se il problema è un circuito di retroazione strettamente interconnesso che non può essere rappresentato responsabilmente come gerarchia, oppure se basta un elenco semplice o un calcolo diretto. Non mescolare cause e soluzioni allo stesso livello, non nascondere lacune rilevanti con «altro» e non continuare a dividere un ramo quando la prossima azione è già chiara.

## Inputs to establish

Stabilisci domanda radice, tipo di albero (`why`, `how` o `what`), misura di successo, ambito, fatti noti e verifiche disponibili. Scegli l'asse di scomposizione del primo livello e registra perché è adatto. Poni al massimo una domanda decisiva se radice o tipo cambiano l'analisi; altrimenti formula una radice delimitata.

## Procedure

1. Pubblica una domanda radice misurabile e il tipo di albero scelto. Indica ambito e misura di successo: costituiscono la base visibile dell'albero.
2. Pubblica i rami del primo livello usando un solo asse di scomposizione ed etichettandolo. Registra se ogni ramo è osservato, inferito o candidato da verificare.
3. Pubblica il livello successivo soltanto quando una divisione più fine cambia un'azione o un test. A ogni livello mostra il controllo di esclusività reciproca e copertura come aggiornamento di stato.
4. Pubblica le foglie, ciascuna con un metodo di verifica, richiesta di dati, responsabile o prossima azione. Una foglia ancora astratta non è terminale; mantieni l'albero aperto o restringi la radice.
5. Pubblica i rami potati e il motivo di ogni potatura, come prove contrarie, esclusione dall'ambito o copertura duplicata. Non eliminare un ramo soltanto perché scomodo.
6. Pubblica una priorità fondata su rilevanza, prove e possibilità di agire, non su precisione numerica inventata. Indica i rami che richiedono un metodo causale o probatorio distinto.
7. Pubblica albero completo, lacune di copertura e una condizione osservabile che cambierebbe la conclusione. Se un ramo critico non è né testabile né delimitato, sospendi il giudizio o poni una domanda bloccante.

## Public output contract

Restituisci `root_question`, `tree_type`, `decomposition_axis`, `mutually_clear_branches`, `branches`, `leaf_tests`, `leaves_with_tests`, `pruned_branches_and_reasons`, `coverage_gaps`, `priority_order` e `flip_condition`. Il risultato pubblico deve mostrare rami reciprocamente chiari, copertura complessivamente pertinente e foglie eseguibili. I fondamenti della scheda usano etichette **verificato**, **calcolato**, **inferito**, **assunto**, **non verificato** o **contrastante**. Non presentare l'albero stesso come prova di un'affermazione causale.

## Evidence and uncertainty rules

ME e CE sono verifiche separate: assenza di sovrapposizione non implica copertura, e copertura non implica assenza di sovrapposizione. Una formula familiare è una struttura candidata finché i suoi presupposti non corrispondono al dominio. Le prove o il test di ciascuna foglia devono essere identificabili; rami privi di sostegno restano ipotesi. Se i rami confliggono o un ramo mancante potrebbe cambiare la decisione, dichiara la lacuna e sospendi o riduci la forza della conclusione.

## Stop conditions

Fermati e poni una domanda bloccante quando domanda radice o tipo non possono essere delimitati e le alternative condurrebbero a lavori differenti. Sospendi se una lacuna rilevante di copertura non ha un test o i rami sono tanto interdipendenti da rendere fuorviante una gerarchia. Fermati quando le foglie hanno azioni chiare e il lavoro restante appartiene a un metodo causale, probatorio o decisionale.

## Complement handoff

Passa a `root-cause-analysis` quando il ramo scelto riguarda un guasto ricorrente e richiede una catena causale invece di ulteriore scomposizione. Trasmetti radice, ramo selezionato, lacune probatorie e test delle foglie. Il complemento non deve ricostruire rami non pertinenti.

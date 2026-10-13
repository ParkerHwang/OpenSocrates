## Purpose

Usa questa procedura per trasformare un'affermazione, una spiegazione o un piano preferito in una previsione rischiosa e verificabile e specificare che cosa conterebbe contro di essa. Separa l'affermazione da valutare dalle assunzioni ausiliarie e dagli errori di misurazione, poi riporta che cosa il test osservato può e non può stabilire. Una previsione fallita è un'evidenza contro l'assetto testato; non confuta automaticamente ogni idea collegata.

## Use when

Usala quando un'affermazione dovrebbe produrre una previsione rischiosa, quando l'utente chiede che cosa potrebbe dimostrare che una spiegazione è sbagliata o quando racconti a posteriori vengono scambiati per previsioni. È adatta a ipotesi di ricerca, piani di prodotto, spiegazioni diagnostiche e affermazioni forti che richiedono un tentativo decisivo di confutazione.

## Do not use when

Non usarla quando non è possibile formulare un'implicazione verificabile, quando il compito riguarda una scelta di valore o un'esecuzione puramente meccanica, o quando l'affermazione è soltanto una definizione. Non considerare la verificabilità una prova, non salvare ogni previsione fallita con un'assunzione ausiliaria ad hoc e non scartare una teoria complessa dopo un solo fallimento senza controllare la misurazione e le condizioni ausiliarie.

## Inputs to establish

Stabilisci affermazione da valutare, ambito, previsione rischiosa, finestra di osservazione, misurazione, assunzioni ausiliarie, soglia di falsificazione e decisione interessata. Indica se il test è pianificato, osservato o non disponibile. Poni al massimo una domanda decisiva quando la previsione o la soglia non può essere altrimenti delimitata.

## Procedure

1. Pubblica l'affermazione e il suo ambito, poi riscrivila come una previsione rischiosa che potrebbe fallire. Questo crea l'oggetto visibile del test, anziché una spiegazione a posteriori.
2. Pubblica il falsificatore: un risultato, una soglia o un andamento osservabile che conterebbe contro l'affermazione. Escludi condizioni vaghe come «evidenze inattese».
3. Pubblica assunzioni ausiliarie e condizioni di misurazione separatamente dall'affermazione da valutare. Indica quale fallimento chiamerebbe in causa l'affermazione, l'assetto o la misurazione.
4. Pubblica il test pianificato o osservato, la sua provenienza e il risultato. Se il test non è disponibile, indica l'osservazione necessaria e mantieni lo stato unverified.
5. Pubblica l'interpretazione: supportata per questo test, indebolita, non ancora testata o inconcludente. Non trasformare un risultato che non falsifica l'affermazione in una forte conferma.
6. Pubblica ogni correzione proposta e controlla se era stata specificata prima del risultato o aggiunta ad hoc. Una correzione che rende l'affermazione immune alla confutazione senza supporto indipendente resta una debolezza.
7. Pubblica lo stato corrente, il prossimo test e una condizione osservabile che cambierebbe il giudizio. Se non può essere dichiarato un falsificatore, sospendi o rifiuta il metodo anziché fabbricare un linguaggio dall'apparenza scientifica.

## Public output contract

Restituisci `claim`, `scope`, `risky_prediction`, `falsifier`, `auxiliary_assumptions`, `measurement_conditions`, `observed_needed_test`, `test_and_provenance`, `observed_or_needed_result`, `status` e `flip_condition`. Il risultato deve distinguere non testato, inconcludente, indebolito e supportato per questo test. I fondamenti usano le etichette **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; un'affermazione non falsificata non è automaticamente verificata.

## Evidence and uncertainty rules

Un falsificatore deve essere osservabile e collegato a un ambito dell'affermazione specificato in anticipo. Un test fallito può riguardare un'assunzione ausiliaria o la misurazione anziché l'intera teoria. Non contare una modifica a posteriori come supporto indipendente. Se il test non è stato eseguito o la soglia è stata scelta dopo aver visto il risultato, etichetta la conclusione unverified o conflicted e indica il limite.

## Stop conditions

Interrompi e poni una domanda bloccante quando l'affermazione o la previsione non può essere delimitata. Rifiuta o sospendi quando non esiste un'implicazione verificabile, l'osservazione necessaria non è disponibile o un'affermazione ad alto impatto non ha un test sicuro. Interrompi quando il compito riguarda qualità delle fonti, conseguenza formale o generazione di spiegazioni anziché un tentativo di confutazione.

## Complement handoff

Passa a `lean-startup` soltanto quando l'affermazione falsificabile è un'ipotesi di prodotto o di mercato e la prossima decisione riguarda un test minimo sicuro. Trasmetti previsione rischiosa, falsificatore, condizioni di misurazione ed esclusioni di sicurezza. Il complemento non deve sostituire un falsificatore mancante con un esperimento generico.

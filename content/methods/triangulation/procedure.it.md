## Purpose

Usa questa procedura per confrontare flussi di evidenze indipendenti, affinché una fonte, metodo, teoria o ricercatore non riceva più fiducia di quanto meriti. Definisce affermazione ed evidenze necessarie, verifica l’indipendenza anziché contare citazioni e riporta convergenze, conflitti e lacune. L’accordo è informativo solo se i flussi differiscono in modo significativo e sono pertinenti alla stessa affermazione.

## Use when

Usala se una singola fonte o metodo può essere distorto, evidenze qualitative e quantitative sono mescolate, o parti interessate offrono ricostruzioni concorrenti. È adatta a verificare affermazioni importanti, valutare programmi, sintetizzare ricerche e prendere decisioni in cui conferme o conflitti cambierebbero l’azione.

## Do not use when

Non usarla se tutte le fonti ripetono lo stesso insieme di dati sottostante, la questione è una preferenza di valore o una regola formale diretta decide il caso. Non contare copie dello stesso rapporto come indipendenti, eliminare un conflitto facendo la media o raccogliere flussi che rispondono ad affermazioni diverse senza dichiarare la discrepanza.

## Inputs to establish

Stabilisci affermazione centrale, decisione, tipi di evidenze richiesti, flussi candidati, fonti comuni a monte, metodi, ricercatori, finestre temporali e rischi rilevanti di distorsione. Scegli l’asse di diversità — dati, metodo, teoria o ricercatore — e spiega perché può verificare l’affermazione. Poni al massimo una domanda decisiva se l’affermazione o il confine di indipendenza non sono chiari.

## Procedure

1. Pubblica l’affermazione centrale e la decisione che potrebbe cambiare. Indica le evidenze necessarie a sostenerla e il suo ambito; ciò crea lo stato visibile della corroborazione.
2. Pubblica ciascun flusso con origine dei dati, metodo, ricercatore, popolazione, periodo e distorsione attesa. Segnala gli input forniti dall’utente, controllati, inferiti e non disponibili.
3. Pubblica la verifica d’indipendenza: dati condivisi, misurazione condivisa, istituzione comune, modello comune o fonte realmente separata. Non trattare la varietà metodologica come indipendenza se tutti i flussi ereditano gli stessi dati grezzi.
4. Pubblica il risultato di ogni flusso rispetto alla stessa affermazione: converge, è in conflitto o non la affronta. Indica direzione e rilevanza di ciascun risultato anziché contare voti.
5. Pubblica lacune e spiegazioni plausibili dei conflitti, incluse differenze di ambito, tempistica, misurazione, selezione e analisi. Mantieni visibili le spiegazioni concorrenti finché una verifica non le risolve.
6. Pubblica lo stato combinato delle evidenze e una conclusione calibrata. L’accordo può rafforzare un risultato sostenuto; un conflitto rilevante lo indebolisce o sospende, salvo che una regola giustificata di precedenza o ambito risolva la disputa.
7. Pubblica la prossima verifica indipendente e una condizione osservabile di cambiamento. Se i flussi non sono indipendenti o non riguardano la stessa affermazione, dichiara insufficiente la triangolazione anziché riportare una falsa corroborazione.

## Public output contract

Restituisci `focal_claim`, `evidence_needed`, `evidence_streams`, `independence_check`, `stream_results`, `agreement_conflict`, `agreement_conflict_gap`, `combined_evidence_state`, `calibrated_conclusion` e `flip_condition`. La scheda deve riassumere convergenza o conflitto e nominare i collegamenti pertinenti alle fonti o etichette sicure fornite dall’utente. Le ragioni usano **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**.

## Evidence and uncertainty rules

L’indipendenza riguarda dati, misurazioni, incentivi e discendenza analitica condivisi, non il numero di citazioni. Un flusso che non affronta l’affermazione centrale è una lacuna, non un’evidenza negativa. L’accordo di flussi dipendenti non giustifica una corroborazione forte. Se flussi rilevanti sono in conflitto, preservalo e sospendi o indebolisci il risultato finché ambito, qualità o precedenza non siano giustificati.

## Stop conditions

Fermati e poni una domanda bloccante se non sono definibili l’affermazione centrale o il confine d’indipendenza. Sospendi se tutti i flussi condividono una fonte non verificata, un conflitto rilevante è irrisolto o i flussi rispondono a domande diverse. Fermati se il compito riguarda solo la classificazione delle fonti, una scelta di valore o un’implicazione formale.

## Complement handoff

Passa a `evidence-hierarchy` se la disputa residua riguarda qualità, disegno o applicabilità di singoli flussi. Trasmetti inventario dei flussi, verdetto sull’indipendenza, sintesi di convergenze e conflitti e verifica mancante. Il complemento non deve dedurre l’indipendenza dal numero di fonti.

## Purpose

Usa questa procedura per aggiornare la fiducia in ipotesi concorrenti quando arrivano nuove prove e la base a priori e la direzione della verosimiglianza possono essere dichiarate responsabilmente. Rende visibili frequenze di base, direzione delle prove, variazione a posteriori e sensibilità. Le probabilità esatte sono facoltative: un aggiornamento ordinale è onesto quando gli input numerici non hanno provenienza, mentre un valore a posteriori preciso deve mostrare input e normalizzazione.

## Use when

Usala per segnali diagnostici, interpretazione di test, prove sequenziali, stime di rischio e decisioni in cui una nuova osservazione dovrebbe cambiare la fiducia in ipotesi concorrenti. È adatta a domande sulla probabilità di un'ipotesi dopo le prove, soprattutto quando si rischia di trascurare la frequenza di base.

## Do not use when

Non usarla senza una base a priori difendibile o almeno una direzione ordinale delle differenze probatorie tra ipotesi, o quando il compito applica una regola rigorosa. Non confondere `P(E|H)` con `P(H|E)`, non riutilizzare le stesse prove come aggiornamenti indipendenti e non inventare percentuali esatte per creare falsa certezza.

## Inputs to establish

Stabilisci ipotesi mutuamente esclusive e sufficientemente esaustive, decisione attuale, base a priori o frequenza di base, nuove prove, direzione o valori della verosimiglianza per ciascuna ipotesi, dipendenze tra prove e soglia d'azione. Fai al massimo due domande decisive quando una base a priori o definizione delle prove mancante cambia l'aggiornamento; altrimenti usa una base ordinale etichettata.

## Procedure

1. Pubblica l'insieme delle ipotesi concorrenti e la soglia decisionale. Indica ciò che aggiorni e contrassegna le ipotesi come fornite dall'utente, sostenute da fonti o provvisorie: questo crea lo stato visibile dell'aggiornamento.
2. Pubblica la base a priori per ogni ipotesi, includendo fonte della frequenza di base, popolazione di riferimento o base ordinale delimitata. Se sconosciuta, mostra l'incertezza invece di scegliere un numero conveniente.
3. Pubblica ciascun elemento probatorio e la sua direzione per ogni ipotesi: sostiene, indebolisce o è sostanzialmente neutro. Verifica se gli elementi sono indipendenti o riutilizzano in parte lo stesso segnale.
4. Pubblica la variazione a posteriori usando aritmetica esatta soltanto con input difendibili; altrimenti indica aggiornamento qualitativo o intervallo. Mostra la normalizzazione delle ipotesi concorrenti e preserva la direzione dal valore a priori a quello a posteriori.
5. Pubblica la sensibilità alle ipotesi sulla base a priori e la verosimiglianza. Identifica la variazione di valore o direzione che invertirebbe la graduatoria o la soglia d'azione.
6. Pubblica l'ipotesi attualmente prevalente, stato a posteriori e prossime prove che migliorerebbero maggiormente la decisione. Mantieni visibile un'ipotesi meno favorita ma plausibile quando resta rilevante.
7. Pubblica la conclusione aggiornata e una condizione osservabile di revisione. Se manca base a priori o direzione della verosimiglianza, sospendi o mantieni provvisorio il risultato, anziché riportare un valore a posteriori inventato.

## Public output contract

Restituisci `hypotheses`, `prior_basis`, `evidence_direction`, `posterior_change`, `normalization_or_update_range`, `sensitivity`, `decision_threshold` e `flip_condition`. La scheda deve distinguere un valore a posteriori calcolato da un aggiornamento ordinale o inferito. I fondamenti usano etichette **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; una frequenza di base non è automaticamente verificata perché numerica.

## Evidence and uncertainty rules

La base a priori deve derivare da frequenza di base difendibile, stima esperta con provenienza o precedente valore a posteriori. La verosimiglianza è `P(E|H)`, non la probabilità dell'ipotesi dopo le prove. Non aggiornare due volte su prove dipendenti. Se input credibili discordano, mostra il conflitto e indebolisci o sospendi il risultato. Se la sensibilità attraversa la soglia d'azione, dichiara fragile la decisione.

## Stop conditions

Fermati e fai una domanda bloccante quando manca l'insieme delle ipotesi o la definizione delle prove e scelte diverse invertirebbero l'azione. Sospendi senza base a priori o direzione della verosimiglianza difendibili, o quando la dipendenza impedisce un aggiornamento affidabile. Fermati se il compito effettivo è una regola rigorosa, ricerca di spiegazioni o graduatoria della qualità delle fonti.

## Complement handoff

Passa a `abduction` quando il compito irrisolto principale è generare e confrontare spiegazioni, anziché aggiornare un insieme definito di ipotesi. Trasmetti prove osservate, ipotesi candidate e verifica discriminante. Il complemento non deve ripetere il calcolo a posteriori.

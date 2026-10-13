## Purpose

Usa questa procedura per scegliere un'azione che rimanga accettabile in più futuri plausibili quando nessuna previsione singola merita di determinare la decisione. Rende visibili incertezza, criteri di fallimento e compromessi, distinguendo una prima mossa robusta da azioni che dovrebbero attendere un segnale. Robusto non significa ottimale in ogni futuro, ma capace di superare la soglia dichiarata senza dipendere da distribuzioni di probabilità inventate.

## Use when

Usala per scelte durature di politica, infrastrutture, investimenti, prodotto o operazioni esposte a incertezze interagenti. È adatta se il fallimento è costoso, la reversibilità lenta o le parti interessate non concordano su una previsione. Serve a chiedersi «cosa può sopravvivere a diverse condizioni plausibili?» invece di «quale risultato è più probabile?».

## Do not use when

Non usarla se un unico caso atteso è affidabile e la scelta è economica e pienamente reversibile, o se esiste una sola azione fattibile imposta da una regola. Non creare cataloghi di casi peggiori arbitrari, dichiarare un'azione migliore in tutti i futuri o nascondere il costo della robustezza. Se successo e fallimento non sono definibili, chiarisci prima la decisione o usa un metodo probatorio per stabilire i criteri.

## Inputs to establish

Stabilisci decisione, azioni fattibili, orizzonte, parti interessate e prestazioni minime accettabili. Definisci fallimento, rimpianto inaccettabile e compromessi rilevanti prima dei test. Elenca incertezze profonde, dipendenze, vincoli noti e poche descrizioni di mondi plausibili; non assegnare probabilità senza una fonte difendibile fornita dall'utente. Registra reversibilità, costo, tempi e impegni attuali. Poni al massimo due domande decisive solo se cambiano insieme delle azioni o soglia di accettazione.

## Procedure

1. Pubblica quadro decisionale, azioni candidate e criteri di accettazione. **Risultato visibile/cambiamento di stato:** il compito ha scelte delimitate e una soglia esplicita di accettabilità/fallimento.
2. Pubblica registro delle incertezze e mondi plausibili distinti, internamente coerenti. **Risultato visibile/cambiamento di stato:** l'analisi passa da una previsione a test visibili; le descrizioni riportano presupposti e dipendenze, non probabilità.
3. Testa ogni azione candidata in ogni mondo secondo i criteri dichiarati. **Risultato visibile/cambiamento di stato:** una matrice strategia-mondo registra stati accettabili, fragili o falliti con etichette delle prove.
4. Pubblica condizioni di fallimento, esposizione al rimpianto e gruppi di mondi che mettono sotto pressione la stessa azione. **Risultato visibile/cambiamento di stato:** vulnerabilità e compromessi sono nominati invece di essere nascosti in un punteggio complessivo.
5. Pubblica l'azione robusta o il più piccolo insieme che supera la soglia nei mondi testati. **Risultato visibile/cambiamento di stato:** distingui raccomandazione da costo, opportunità perse e vulnerabilità residua.
6. Pubblica salvaguardie, prime mosse reversibili, azioni condizionate e segnali di monitoraggio con relative risposte ai trigger. **Risultato visibile/cambiamento di stato:** la decisione diventa adattiva anziché una scommessa unica sul mondo preferito.
7. Pubblica stato sostenuto, provvisorio o sospeso e condizione osservabile di cambiamento. **Risultato visibile/cambiamento di stato:** criteri o mondi decisivi mancanti producono sospensione, non una dichiarazione di robustezza.

## Public output contract

Restituisci `uncertainties`, `plausible_worlds`, `regret_or_failure_criteria`, `robust_action`, `tradeoffs`, `monitoring_signals`, `flip_condition` e stato sostenuto, provvisorio o sospeso. Descrivi perché l'azione supera la soglia e dove resta fragile. La scheda formula una conclusione, etichetta fondamenti rilevanti, nomina l'incertezza irrisolta e dà una condizione osservabile che cambierebbe l'azione; matrici dettagliate appartengono alla traccia o all'artefatto di supporto.

## Evidence and uncertainty rules

I mondi plausibili sono casi di test strutturati, non previsioni né campioni ponderati per probabilità. Fonda ogni mondo rilevante su osservazione, meccanismo difendibile, vincolo dell'utente o presupposto esplicito. Non inventare frequenze, perdite attese, utilità o robustezza universale. «Accettabile» deve riferirsi al criterio pubblicato. Mostra dati e unità dei confronti calcolati e conserva prove contrastanti senza attenuarle artificialmente. Un'azione robusta può essere inferiore per costo o potenziale guadagno: rendi visibile il compromesso.

## Stop conditions

Poni una domanda bloccante e fermati se insieme delle azioni o prestazioni minime ammettono interpretazioni sostanzialmente diverse. Sospendi se mancano incertezza decisiva, soglia di fallimento o azione fattibile. Ferma il metodo quando una previsione singola è affidabile, una regola vincolante non lascia discrezionalità o resta costruzione di scenari, verifica delle prove o normale confronto di opzioni.

## Complement handoff

Passa a `scenario-planning` quando i mondi richiedono una struttura più deliberata di futuri esterni o una narrazione dei segnali. Trasmetti quadro decisionale, registro delle incertezze, soglia di accettazione, gruppi vulnerabili e descrizioni attuali. Il complemento arricchisce i mondi senza nascondere criteri di fallimento o trasformarli in probabilità.

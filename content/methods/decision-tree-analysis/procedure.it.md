## Purpose

Usa questa procedura per rappresentare decisioni che si sviluppano nel tempo, dove azioni cambiano possibilità successive ed eventi incerti conducono a ulteriori scelte. Separa nodi decisionali, aleatori e di esito per rendere tracciabile la raccomandazione alle informazioni. Può calcolare a ritroso con valori e probabilità delimitati, ma deve sospendere anziché fabbricare precisione quando i rami non sono sostenibili.

## Use when

Usala per lanci graduali, scelte tra progetto pilota ed espansione, tempi di manutenzione o sostituzione, attesa di test e altre decisioni con rami condizionati. È adatta quando conta l'ordine delle azioni, scelte successive dipendono da risultati osservati ed esiti hanno valori sostenuti da fonti o conseguenze qualitative etichettate. L'albero serve quando la domanda riguarda strategie disponibili dopo nuove informazioni, non soltanto quale opzione prevalga ora.

## Do not use when

Non usarla per confronti statici senza sequenza o rami aleatori significativi, diagrammi meccanici o regole vincolanti senza discrezionalità. Non disegnare rami indipendenti per eventi con causa comune o dipendenti da esiti precedenti. Non calcolare valori attesi senza delimitare probabilità, valori d'esito o azioni condizionali. Se domina incertezza profonda con futuri esterni coerenti, passa a scenario-planning.

## Inputs to establish

Indica punto decisionale, azioni possibili, tempi d'osservazione, eventi aleatori, esiti terminali, punti di ripristino e persona o sistema autorizzato ad agire a ciascun nodo. Registra provenienza delle probabilità, unità, tempi, costi, benefici e dipendenze tra rami. Indica probabilità come verified, computed da dati dichiarati, inferred, assumed, unverified o conflicted. Fai al massimo due domande decisive, come «Quale osservazione cambia la prossima azione disponibile?» e «Quale fonte delimita questo ramo?».

## Procedure

1. **Fissa la sequenza.** Indica decisione, ordine di azioni e osservazioni, orizzonte temporale e punti disponibili di ripristino o arresto. **Risultato visibile/cambiamento di stato:** pubblica quadro dell'albero con nodi noti etichettati decisione, caso, osservazione o esito.
2. **Enumera i rami condizionali.** Per ogni nodo decisionale elenca azioni ancora fattibili; per ciascun nodo aleatorio esiti mutuamente esclusivi e ciò che consentono dopo. Preserva le dipendenze senza appiattirle in rami estranei. **Risultato visibile/cambiamento di stato:** crea registro con genitore, figlio, condizione e prossima azione.
3. **Descrivi gli esiti terminali.** Attribuisci a ogni ramo conseguenza, unità, tempi, gruppo interessato e stato probatorio. Mantieni vincoli non comparabili di sicurezza o diritti fuori dal valore aggregato. **Risultato visibile/cambiamento di stato:** pubblica registro d'esiti e marca valori mancanti o conflittuali come sospesi o irrisolti.
4. **Delimita l'incertezza.** Allega fonte o calcolo riproducibile a ogni probabilità; verifica completezza dei rami condizionati e compatibilità con l'evento precedente. Se una probabilità non è delimitabile, usa intervallo difendibile o ramo qualitativo soltanto con base dichiarata, senza fingere risposte numeriche. **Risultato visibile/cambiamento di stato:** pubblica mappa di provenienza o nota di sospensione del ramo non delimitato.
5. **Calcola a ritroso e metti alla prova.** Dagli esiti terminali calcola o confronta rami genitori usando valori e unità dichiarati. Varia probabilità o esiti rilevanti entro intervalli difendibili e mostra esposizione peggiore, rimpianto o soglia di ripristino anziché affidarti a un unico valore atteso. **Risultato visibile/cambiamento di stato:** pubblica tabella a ritroso con azione raccomandata, condizione di cambio e rischio residuo.
6. **Fissa la strategia.** Spiega azione sostenuta ora, osservazione che attiverebbe un'altra azione e punto di pausa. Se un ramo irrisolto può cambiare strategia, sospendi la raccomandazione e indica la minima osservazione sicura. **Risultato visibile/cambiamento di stato:** pubblica nodi decisionali/aleatori/d'esito, riepilogo esiti, provenienza probabilistica, ripristino, incertezza e condizione di revisione della Conclusion Card.

## Public output contract

Restituisci nodi decisionali, aleatori e d'esito, rami condizionati, conseguenze terminali e punto di ripristino. Mostra provenienza probabilistica per ogni ramo numerico e unità ed espressioni dei valori calcolati. Includi esposizione al rischio, condizione di cambio o arresto e prossima osservazione se la strategia è provvisoria. La conclusione pubblica non deve implicare che un albero dimostri un esito; aritmetica dettagliata e dipendenze appartengono alla traccia.

## Evidence and uncertainty rules

Usa verified soltanto con fonte identificabile favorevole al ramo o esito, computed per aritmetica trasparente da input dichiarati, inferred per conseguenze da fondamenti etichettati, assumed per premesse esplicite di piano, unverified per input non controllati e conflicted quando fonti credibili discordano. Non inventare frequenze di base, probabilità, utilità, indipendenza o valori terminali. Se i rami non sono mutuamente esclusivi, correggi la struttura prima di calcolare. Intervalli stretti senza provenienza sono falsa precisione.

## Stop conditions

Sospendi quando sequenza, prossima azione, esito di ramo o base probabilistica mancano in modo capace di cambiare strategia. Sospendi se le dipendenze non sono rappresentabili senza doppio conteggio o una regola vincolante elimina discrezionalità. Se lo spazio dei rami è troppo aperto, indica l'osservazione mancante e passa a scenario-planning anziché produrre valori attesi non sostenuti.

## Complement handoff

Passa a scenario-planning quando futuri esterni coerenti, anziché rami aleatori delimitati, determinano la preparazione. Trasmetti soltanto quadro decisionale, incertezze rilevanti, segnali dei rami e azioni utili comunque o condizionate; escludi probabilità non sostenute e deliberazioni private.

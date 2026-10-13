## Purpose

Usa questa procedura per testare come cambiano risultato di un modello, confronto o decisione al variare di dati o pesi importanti entro intervalli difendibili. Identifica variabili influenti, valori di cambio, interazioni e presupposti fragili. Il risultato è una verifica trasparente di robustezza, non un permesso di scegliere intervalli drammatici o suggerire che un modello dimostri il futuro.

## Use when

Usala quando esistono calcolo, modello previsionale, business case, regola di punteggio o confronto di opzioni e dati incerti possono cambiare la decisione. Aiuta a dare priorità alla raccolta dei dati, esporre soglie nascoste e distinguere conclusioni che resistono a variazioni ragionevoli da quelle dipendenti da un presupposto ristretto. Può usare variazioni numeriche o ordinali con scala esplicita.

## Do not use when

Non usarla senza modello, confronto, regola decisionale o relazione fra variabili da perturbare. Non creare risultati da domande puramente fattuali, riferimenti iniziali indefiniti o intervalli senza provenienza. Non variare indipendentemente variabili correlate, trattare modelli non lineari come lineari senza verifica o fornire un valore di cambio preciso se i dati non sostengono quella precisione.

## Inputs to establish

Stabilisci modello o regola iniziale, metrica del risultato, soglia decisionale, dati o pesi, unità e risultato attuale. Definisci intervallo plausibile e provenienza per ciascun dato incerto, con dipendenze e vincoli. Indica disegno delle perturbazioni, arrotondamento e tipo di test: una variabile per volta, combinazione strutturata o confronto ordinale. Registra opzione o politica informata dal risultato. Poni al massimo due domande decisive solo quando cambiano riferimento o intervallo.

## Procedure

1. Pubblica formula o regola iniziale, dati, unità e risultato. **Risultato visibile/cambiamento di stato:** esistono stato iniziale riproducibile e soglia decisionale nominata.
2. Pubblica intervalli testati, pesi, dipendenze e prove per ogni intervallo. **Risultato visibile/cambiamento di stato:** ogni limite della perturbazione è verificato, calcolato, inferito, assunto, non verificato o contrastante, non scelto per impressionare.
3. Esegui test su una variabile per volta e poi solo combinazioni strutturate difendibili. **Risultato visibile/cambiamento di stato:** un registro indica dato cambiato, risultato, metodo, unità e arrotondamento; dati correlati cambiano insieme quando necessario.
4. Pubblica direzione, entità o cambiamento ordinale della risposta, interazioni e valori di cambio dove si supera la soglia. **Risultato visibile/cambiamento di stato:** le variabili sono classificate influenti, non influenti, robuste o fragili senza fingere che l'ordine dimostri causalità.
5. Pubblica implicazione decisionale e priorità di ricerca per le variabili capaci di cambiarla. **Risultato visibile/cambiamento di stato:** lo sforzo d'indagine è collegato a una condizione di cambiamento nominata, non alla maggiore variazione grezza.
6. Pubblica conclusione robusta, fragile, provvisoria o sospesa con prossima verifica di validazione. **Risultato visibile/cambiamento di stato:** riferimento, intervallo o soglia mancanti producono sospensione esplicita, non affermazioni inventate di sensibilità.

## Public output contract

Restituisci `baseline`, `tested_ranges`, `perturbation_results`, `switching_values`, `robust_or_fragile_conclusion`, `research_priority` e `flip_condition`, con stato sostenuto, provvisorio o sospeso. Indica soglia e dati capaci di superarla. I fondamenti della scheda identificano valori calcolati e dati usati; l'incertezza nomina limiti di intervallo o modello; la condizione di cambiamento è una variazione osservabile di dato o soglia. Conserva registro completo e formule nella traccia o artefatto di supporto.

## Evidence and uncertainty rules

Gli intervalli richiedono fonte, vincolo dell'utente, osservazione storica o presupposto esplicito; un intervallo comodo non è una prova. I risultati calcolati espongono formula, operandi, unità e arrotondamento. Conserva non linearità, correlazione, discontinuità e incertezza sulla forma del modello quando rilevanti. Se sono difendibili solo pesi ordinali, riporta direzione o ordine delle soglie, non percentuali falsamente precise. Non inferire probabilità reali dalla frequenza di campionamento dei casi di test. Un risultato robusto può ancora produrre una decisione fragile se soglia o obiettivo sono sbagliati.

## Stop conditions

Poni una domanda bloccante e fermati se riferimento iniziale, soglia o risultato obiettivo hanno interpretazioni sostanzialmente diverse. Sospendi se non si stabiliscono intervallo necessario, dipendenza o regola. Ferma il metodo quando nessuna perturbazione difendibile cambierebbe la decisione o resta verifica delle prove, spiegazione causale o confronto più ampio di compromessi.

## Complement handoff

Passa a `trade-off-analysis` se i risultati devono combinarsi con criteri, pesi e preferenze delle parti interessate espliciti fra opzioni. Trasmetti riferimento iniziale, valori di cambio, risultati robusti/fragili, provenienza degli intervalli e priorità di ricerca. Il complemento confronta scelte entro quei limiti senza trattare l'ordine di sensibilità come preferenza o probabilità.

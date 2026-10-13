## Purpose

Usa questa procedura per strutturare più futuri esterni coerenti e prepararvi le scelte. Non mira a prevedere un futuro unico, ma a mostrare come si comporta una decisione quando forze importanti e incerte divergono. Il risultato separa azioni utili indipendentemente dallo scenario e azioni condizionate, mantenendo visibili i segnali per revisioni successive.

## Use when

Usala per scelte a lungo termine di strategia, investimenti, politiche, infrastrutture o prodotti, soprattutto con orizzonti di almeno cinque anni o previsioni fallite ripetutamente. Risponde a «a cosa dobbiamo prepararci?» quando diverse condizioni esterne possono plasmare il risultato. Serve prima di impegni irreversibili, non solo dopo aver scelto una previsione.

## Do not use when

Non usarla per previsioni puntuali brevi, semplici variazioni numeriche ottimistiche/di base/pessimistiche o decisioni senza incertezza esterna significativa. Non scegliere due assi correlati, scrivere quattro versioni dello stesso futuro buono/cattivo, assegnare probabilità o terminare con storie senza azioni. Per confrontare dati numerici in un modello, usa invece sensitivity analysis.

## Inputs to establish

Stabilisci domanda focale, orizzonte, confine del sistema, decisione attuale e premesse comuni abbastanza prevedibili da mantenersi nei futuri. Elenca fattori candidati con prove di impatto e incertezza, identificando due incertezze critiche indipendenti. Registra vincoli, parti interessate, impegni esistenti e osservazioni che possono diventare segnali. Poni al massimo due domande decisive solo se cambiano domanda focale o coppia di assi. Etichetta premesse e fattori come verificati, calcolati, inferiti, assunti, non verificati o contrastanti.

## Procedure

1. Pubblica domanda focale, orizzonte, confine, decisione attuale e premesse comuni. **Risultato visibile/cambiamento di stato:** il lavoro passa da richiesta aperta sul futuro a domanda delimitata di preparazione.
2. Pubblica i due assi d'incertezza critica e perché hanno alto impatto e scarsa prevedibilità. **Risultato visibile/cambiamento di stato:** candidati correlati, poco influenti o prevedibili sono scartati o spostati nelle premesse comuni.
3. Pubblica una matrice 2×2 con quattro scenari nominati internamente coerenti e un breve percorso di formazione per ciascuno. **Risultato visibile/cambiamento di stato:** esistono quattro futuri distinti come ambienti plausibili di test, senza probabilità né etichette di preferenza.
4. Pubblica validità e vulnerabilità della decisione attuale in ogni scenario. **Risultato visibile/cambiamento di stato:** il registro di stress test distingue azioni utili in tutti gli scenari, azioni condizionate e scelte che falliscono nella matrice.
5. Pubblica segnali, risposte ai trigger e cadenza di revisione per distinguere scenari durante l'evoluzione delle condizioni. **Risultato visibile/cambiamento di stato:** gli scenari diventano piano vivo di monitoraggio, non narrazione statica.
6. Pubblica conclusione di robustezza e condizione osservabile di cambiamento. **Risultato visibile/cambiamento di stato:** se assi, premesse o implicazioni operative non sono difendibili, la conclusione diventa provvisoria o sospesa, non una previsione mascherata.

## Public output contract

Restituisci `driving_uncertainties`, `scenarios`, `signposts`, `no_regret_actions`, `contingent_actions`, `decision_check` e `flip_condition`, con stato sostenuto, provvisorio o sospeso. `scenarios` contiene quattro sintesi nominate con percorsi e implicazioni decisionali. La scheda indica conclusione preparatoria, incertezza rilevante, condizione osservabile che cambia il piano e sintesi compatta delle alternative. Mantieni matrice completa e cadenza di revisione nella traccia o artefatto di supporto.

## Evidence and uncertainty rules

Le premesse comuni devono essere sostenute da fonti o esplicitamente assunte. Un asse è un'ipotesi di inquadramento su impatto e incertezza, non un fatto misurato salvo prove corrispondenti. Gli scenari devono essere coerenti e plausibili ma non sono previsioni: non attribuire percentuali, classifiche o probabilità nascoste. Separa segnali osservati e interpretazioni inferite. Non inventare tendenze, date dei trigger o fattori esterni. Se i due assi sono dipendenti, rivedili o sospendi.

## Stop conditions

Poni una domanda bloccante e fermati se domanda focale, orizzonte o confine decisionale hanno significati sostanzialmente diversi. Sospendi senza incertezze indipendenti ad alto impatto, premesse difendibili o decisione traducibile in azioni. Ferma il metodo per previsioni brevi, perturbazioni di modelli o scelte operative definite; reindirizza invece di imporre quattro scenari.

## Complement handoff

Passa a `pestel-analysis` quando i fattori degli scenari richiedono una revisione strutturata degli aspetti politici, economici, sociali, tecnologici, ambientali o legali. Trasmetti domanda focale, orizzonte, premesse comuni, fattori candidati, assi scelti e stati delle prove. Il complemento testa i fattori esterni senza ridurre gli scenari a un unico futuro previsto.

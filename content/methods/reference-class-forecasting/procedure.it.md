## Purpose

Usa questa procedura per sostituire una previsione interna con un confronto esterno fondato su una classe difendibile di casi comparabili completati. Stima un risultato dai valori osservati ed esplicita quali fatti attuali giustifichino aggiustamenti. È un aiuto alla calibrazione, non una promessa né un permesso di inventare popolazione, distribuzione o probabilità.

## Use when

Usala per previsioni di tempi, costi, domanda, adozione, affidabilità o consegna quando sono disponibili casi passati simili e il piano interno può essere ottimistico. È particolarmente utile quando una proposta dichiara «questo caso è diverso» senza mostrare come la differenza cambi l'intervallo atteso. Serve a decisioni che richiedono un intervallo fondato anziché una singola stima puntuale.

## Do not use when

Non usarla senza classe di riferimento difendibile di casi completati, con obiettivo e unità poco chiari o per un caso unico senza risultati comparabili. Pochi aneddoti non sono una distribuzione di base; non selezionare solo successi e non trasformare previsioni interne in prove. Se la decisione è puramente meccanica o richiede diagnosi causale invece di calibrazione, fermati e reindirizza.

## Inputs to establish

Stabilisci risultato obiettivo, unità, orizzonte, data limite e confine accettabile. Definisci regole di inclusione ed esclusione della classe prima di esaminare risultati. Raccogli casi osservati, definizioni dei risultati, copertura, dati mancanti e stato delle fonti. Registra differenze note del progetto corrente e previsione interna. Poni al massimo due domande decisive solo se cambiano classe o obiettivo. Etichetta ogni dato come verificato, calcolato, inferito, assunto, non verificato o contrastante.

## Procedure

1. Pubblica obiettivo, unità, orizzonte e confine decisionale in una frase. **Risultato visibile/cambiamento di stato:** esiste una base previsionale; obiettivi ambigui sono sospesi invece di essere ristretti tacitamente.
2. Pubblica regola della classe di riferimento con inclusioni, esclusioni, dimensioni di somiglianza e lacune note di copertura. **Risultato visibile/cambiamento di stato:** il confronto passa da intuizione a definizione di classe verificabile.
3. Pubblica la distribuzione dei risultati osservati usando soltanto casi disponibili: conteggio, centro, dispersione, intervallo e code se calcolabili. **Risultato visibile/cambiamento di stato:** ogni statistica ha dati espliciti ed etichetta di fonte/prova; statistiche indisponibili restano non verificate.
4. Pubblica il riferimento esterno accanto al piano interno e spiega la direzione della differenza. **Risultato visibile/cambiamento di stato:** registra se il piano è dentro, sopra o sotto la distribuzione osservata senza trattare quella posizione come probabilità.
5. Pubblica aggiustamenti per differenze rilevanti del caso attuale, una alla volta. **Risultato visibile/cambiamento di stato:** ogni aggiustamento ha direzione, motivazione e stato delle prove; usalo numericamente solo con entità difendibile.
6. Pubblica un intervallo delimitato e le condizioni che rendono plausibili gli estremi. **Risultato visibile/cambiamento di stato:** amplia o sospendi l'intervallo se prove di copertura, selezione o code sono deboli; nessun tasso di base inventato colma la lacuna.
7. Pubblica stato sostenuto, provvisorio o sospeso con condizione di cambiamento e prossima verifica. **Risultato visibile/cambiamento di stato:** classe o risultato decisivi mancanti producono sospensione esplicita, non raccomandazioni arbitrarie.

## Public output contract

Restituisci `target`, `reference_class`, `base_distribution`, `adjustments`, `range`, `inside_view_comparison`, `flip_condition` e stato sostenuto, provvisorio o sospeso. La conclusione indica cosa sostiene la classe osservata, non che il caso attuale vi corrisponderà. I fondamenti della scheda usano **verificato**, **calcolato**, **inferito**, **assunto**, **non verificato** o **contrastante**; l'incertezza nomina copertura mancante o rischio di selezione e la condizione di cambiamento è osservabile, non «se emergono nuove informazioni».

## Evidence and uncertainty rules

La classe è sostenuta solo da casi completati con obiettivo, unità e stato d'inclusione definiti. Una fonte può verificare risultati osservati ma non la comparabilità del progetto corrente; etichetta tale confronto come inferito salvo sostegno diretto. I calcoli mostrano casi o riferimenti usati e regola d'arrotondamento. Non inventare mediana, coda, dimensione del campione, tasso di base o probabilità. Conserva distorsione di selezione, casi mancanti, definizioni contrastanti e limiti dei piccoli campioni. «Questo caso è diverso» resta un'ipotesi d'aggiustamento finché direzione ed effetto non hanno prove.

## Stop conditions

Poni una domanda bloccante e fermati se obiettivo, unità o confine decisionale hanno interpretazioni sostanzialmente diverse. Sospendi la conclusione senza classe difendibile, definizione dei risultati o dato comparativo decisivo. Ferma il metodo quando resta spiegazione causale, scelta fra opzioni o calcolo meccanico; trasferisci il lavoro invece di forzare una previsione esterna.

## Complement handoff

Passa a `sensitivity-analysis` quando la decisione dipende da come distribuzione di riferimento o aggiustamento attuale cambiano la scelta. Trasmetti obiettivo, riferimento osservato, intervalli degli aggiustamenti testati, limiti di copertura e condizione di cambio. Il complemento varia quei dati senza ricostruire la classe o trattare il risultato come nuovo tasso di base.

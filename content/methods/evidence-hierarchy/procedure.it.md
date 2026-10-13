## Purpose

Usa questa procedura per calibrare un'affermazione rispetto a qualità, rapporto diretto, applicabilità e rischio di distorsione delle fonti che la supportano. Classifica il tipo di affermazione, confronta disegni di studio o di evidenza senza considerare universale una gerarchia rigida e dichiara lo stato delle evidenze e la forza della conclusione risultanti. Una fonte di livello inferiore può comunque essere utile quando corrisponde direttamente alla domanda e disegni più forti non lo fanno.

## Use when

Usala quando si mescolano ricerca, politiche, esperimenti di prodotto, pareri esperti, resoconti degli utenti o altri tipi di evidenza e la risposta richiede un'etichetta di forza difendibile. È adatta a domande sul supporto delle fonti a un'affermazione, sull'applicabilità di uno studio al contesto di riferimento e su come cambiare la formulazione quando la qualità delle evidenze differisce.

## Do not use when

Non usarla quando la disputa principale riguarda una preferenza di valore anziché il supporto fattuale, o quando è più specifico un metodo su regole formali, modelli causali o conflitti fra fonti. Non ordinare le evidenze soltanto per prestigio, non scartare automaticamente evidenze rilevanti di livello inferiore e non definire forte una fonte senza controllarne rapporto diretto e limiti.

## Inputs to establish

Stabilisci affermazione, popolazione o contesto di riferimento, tipo di affermazione (effetto, previsione, meccanismo o esperienza), soglia decisionale, fonti, disegni degli studi, campioni, misure e conflitti noti. Identifica se ogni fonte è diretta, indiretta o soltanto contestuale. Poni al massimo una domanda decisiva quando il contesto di riferimento cambia l'applicabilità.

## Procedure

1. Pubblica affermazione, contesto di riferimento e soglia decisionale. Indica se l'affermazione riguarda un effetto, una previsione, un meccanismo o un'esperienza; questo crea lo stato visibile dell'esame delle evidenze.
2. Pubblica una tabella che collega affermazioni e fonti, con tipo di fonte, disegno, campione o base, rapporto diretto e ambito. Indica per ogni fonte se è stata controllata, fornita dall'utente, inferita o non disponibile.
3. Pubblica le dimensioni di qualità: rigore del disegno, rischio di distorsione, validità delle misure, completezza e applicabilità. Usa etichette qualitative o ordinali con provenienza. Non inventare un punteggio composito preciso.
4. Pubblica la posizione nella gerarchia e i relativi limiti di ogni fonte. Spiega perché è forte o debole per questa particolare affermazione, anziché considerare la posizione un'autorità universale.
5. Pubblica accordi, incoerenze ed evidenze mancanti fra le fonti. Mantieni visibile un conflitto credibile; non ridurre risultati incompatibili a un'unica media numerica senza una regola di sintesi giustificata.
6. Pubblica lo stato delle evidenze risultante e una formulazione calibrata della conclusione: strongly supported, supported, provisional, unverified, conflicted o held. Indica il più piccolo limite della fonte o dell'applicabilità che vincola la formulazione.
7. Pubblica la prossima azione di verifica e una condizione osservabile che cambierebbe il giudizio. Se manca un supporto decisivo, sospendi o ridimensiona l'affermazione anziché presentare una conclusione ad alto impatto come accertata.

## Public output contract

Restituisci `claim`, `claim_type`, `claim_to_source_table`, `quality_limits`, `quality_dimensions`, `hierarchy_position_and_limits`, `agreement_and_conflicts`, `missing_evidence`, `resulting_evidence_state`, `calibrated_conclusion` e `flip_condition`. La scheda deve mostrare lo stato delle evidenze e, quando pertinente, un collegamento sicuro alla fonte o l'etichetta di contenuto fornito dall'utente. I fondamenti usano le etichette **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**.

## Evidence and uncertainty rules

La gerarchia dei disegni è una guida, non sostituisce la pertinenza alla domanda. Controlla rapporto diretto, popolazione, esito, tempo, misurazione, selezione, abbandoni e distorsioni nella rendicontazione. Un parere esperto può identificare un meccanismo senza stimare la dimensione dell'effetto; un resoconto dell'utente può rivelare un'esperienza senza stabilirne la prevalenza. Se le fonti discordano in modo rilevante o la fonte migliore è indiretta, riduci o sospendi il risultato e indica il limite.

## Stop conditions

Interrompi e poni una domanda bloccante quando il contesto di riferimento o l'affermazione non sono definiti e l'applicabilità cambierebbe la decisione. Sospendi quando nessuna fonte supporta direttamente un'affermazione rilevante, un conflitto non può essere risolto o i limiti di qualità impediscono un'etichetta di forza sicura. Interrompi quando la questione riguarda una scelta di valore, una conseguenza formale o la generazione di spiegazioni anziché la calibrazione delle evidenze.

## Complement handoff

Passa a `triangulation` quando flussi di evidenza indipendenti potrebbero corroborare una conclusione o rivelare un conflitto rilevante. Trasmetti la tabella di collegamento tra affermazioni e fonti, i limiti di qualità e il disaccordo irrisolto. Il complemento deve controllare indipendenza e convergenza senza ricostruire la graduatoria delle fonti.

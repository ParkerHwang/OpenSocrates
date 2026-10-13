## Purpose

Use este procedimento para comparar linhas independentes de evidência, evitando confiança excessiva em uma fonte, método, teoria ou pesquisador. Defina afirmação e evidências exigidas, verifique independência em vez de contar citações e reporte convergência, conflito e lacunas. Acordo informa apenas quando as linhas diferem significativamente e tratam da mesma afirmação.

## Use when

Use quando fonte ou método único possa ter viés, houver evidências qualitativas e quantitativas mistas ou partes interessadas fornecerem relatos concorrentes. Serve à verificação de afirmações importantes, avaliação de programas, síntese de pesquisa e decisões em que corroboração ou conflito mudariam ação.

## Do not use when

Não use se todas as fontes repetirem um conjunto de dados, a questão for preferência de valor ou regra formal direta decidir. Não conte cópias como independentes, elimine conflito por média ou reúna linhas que respondam a afirmações diferentes sem declarar incompatibilidade.

## Inputs to establish

Estabeleça afirmação focal, decisão, tipos de evidência necessários, linhas candidatas, fontes originais comuns, métodos, pesquisadores, janelas e riscos de viés. Escolha eixo de diversidade em dados, método, teoria ou pesquisador e explique sua capacidade de testar afirmação. Faça no máximo uma pergunta decisiva se afirmação ou limite da independência estiverem pouco claros.

## Procedure

1. Publique afirmação focal e decisão que pode mudar. Declare evidência necessária e escopo, criando estado visível da corroboração.
2. Publique cada linha com origem dos dados, método, pesquisador, população, tempo e viés esperado. Marque entradas fornecidas pelo usuário, verificadas, inferidas ou indisponíveis.
3. Publique teste de independência: dados, medição, instituição ou modelo compartilhados, ou fonte realmente separada. Variedade metodológica não implica independência se todas herdarem os mesmos dados brutos.
4. Publique resultado de cada linha sobre a mesma afirmação: converge, conflita ou não trata dela. Declare direção e materialidade, não votos.
5. Publique lacunas e explicações plausíveis do conflito: escopo, momento, medição, seleção e análise. Preserve explicações concorrentes até verificação resolvê-las.
6. Publique estado combinado e conclusão calibrada. Acordo pode fortalecer resultado sustentado; conflito material reduz ou suspende, salvo prioridade ou regra de escopo justificadas.
7. Publique próxima verificação independente e condição observável de mudança. Sem independência ou mesma afirmação, declare triangulação insuficiente em vez de corroboração falsa.

## Public output contract

Retorne `focal_claim`, `evidence_needed`, `evidence_streams`, `independence_check`, `stream_results`, `agreement_conflict`, `agreement_conflict_gap`, `combined_evidence_state`, `calibrated_conclusion` e `flip_condition`. A ficha resume convergência ou conflito e nomeia ligações das fontes ou rótulos seguros fornecidos pelo usuário. Fundamentos usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**.

## Evidence and uncertainty rules

Independência envolve dados, medição, incentivos e linhagem analítica compartilhados, não número de citações. Linha que não responde à afirmação é lacuna, não evidência negativa. Acordo dependente não justifica corroboração forte. Com conflito material, preserve divergência e suspenda ou reduza até justificar escopo, qualidade ou prioridade.

## Stop conditions

Pare e faça uma pergunta bloqueadora sem afirmação ou limite de independência definíveis. Suspenda se todas as linhas compartilharem fonte não verificada, conflito material não tiver solução ou responderem a perguntas diferentes. Pare para classificação isolada de fontes, escolha de valores ou implicação formal.

## Complement handoff

Encaminhe para `evidence-hierarchy` se restar disputa de qualidade, desenho ou aplicabilidade de linhas individuais. Passe inventário, veredicto de independência, convergência/conflito e verificação ausente. O complemento não infere independência pelo número de fontes.

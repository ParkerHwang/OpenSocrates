## Purpose

Use este procedimento para generalizar observações mantendo a conclusão probabilística e limitada pela amostra. Ele identifica tipo de indução, verifica tamanho, diversidade e representatividade, busca ativamente contraexemplos e declara escopo e força da generalização. Observações repetidas só aumentam suporte quando a base de amostragem e medição justifica estendê-las.

## Use when

Use-o para padrões de dados, pesquisas, comentários de usuários, incidentes repetidos e alegações que passam de casos observados a população ampla ou comportamento futuro. Serve para generalização estatística, enumerativa, causal ou analógica quando o usuário precisa saber até onde observações sustentam a alegação.

## Do not use when

Não o use para amostra de conveniência não representativa, aplicação de regra estrita ou alegação causal que exige desenho causal, não extensão de padrão. Não trate muitas observações duplicadas como diversidade, infira “todos” de pequena amostra nem transforme tendência plausível em conclusão necessária.

## Inputs to establish

Estabeleça observações, população-alvo ou escopo futuro, processo amostral, definição de medição, grupos de comparação, período e decisão afetada. Identifique tipo de indução e vieses conhecidos de seleção, sobrevivência, não resposta ou medição. Faça no máximo uma pergunta decisiva se população ou base amostral desconhecida modificar escopo.

## Procedure

1. Publique premissas observadas e generalização proposta como afirmações separadas. Marque proveniência e estado das evidências de cada observação; isso cria referência visível da indução.
2. Publique tipo: enumerativo, estatístico, causal ou analógico, e ponte entre amostra e escopo-alvo. Declare os pressupostos que tornam a ponte plausível.
3. Publique base amostral: tamanho, diversidade, seleção, casos ausentes, qualidade da medição e cobertura temporal. Distinga descrição apoiada por fonte de alegação inferida de representatividade.
4. Publique busca mais forte de contraexemplos e resultado. Inclua casos não selecionados, resultados negativos, diferenças de subgrupos e exceções futuras plausíveis quando disponíveis.
5. Publique generalização delimitada com limite de escopo e força qualitativa, como forte, moderada ou fraca. Substitua linguagem universal por população ou intervalo de proporções apenas com proveniência defensável.
6. Publique consequência decisória e próxima observação que mais melhoraria ou questionaria a generalização. Declare se sustenta ação, monitoramento ou mais amostragem.
7. Publique conclusão atual e condição observável de reversão. Se amostra for enviesada, escassa ou incompatível demais com alvo, suspenda ou mantenha provisório, sem extrapolar.

## Public output contract

Retorne `observations`, `induction_type`, `sample_basis`, `generalization`, `scope_limit`, `counterexample_risk`, `counterexample_search`, `strength`, `decision_consequence` e `flip_condition`. Distinga casos observados da alegação ampla. Fundamentos usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**; normalmente a generalização é inferida, não diretamente verificada.

## Evidence and uncertainty rules

Tamanho amostral isolado não estabelece representatividade. Verifique seleção, cobertura, perdas, medição, equilíbrio de subgrupos e relevância temporal. Contraexemplo pode limitar alegação universal sem provar tendência oposta. Não reutilize observação como suporte independente e teste de contraexemplo. Se base amostral ou escopo-alvo faltar, reduza o apoio ou suspenda.

## Stop conditions

Pare e faça pergunta bloqueante se população-alvo ou processo amostral forem desconhecíveis e escopos diferentes mudarem ação. Suspenda se amostra for materialmente não representativa, alegação causal exceder desenho ou risco decisivo de contraexemplo não estiver resolvido. Pare se tarefa for regra estrita, diagnóstico de hipóteses concorrentes ou comparação de fontes.

## Complement handoff

Encaminhe a `evidence-hierarchy` quando restar saber se amostra ou desenho merece peso suficiente para alegação. Transfira base amostral, generalização, limite de escopo e principal risco de contraexemplo. O complemento não deve repetir o procedimento de generalização.

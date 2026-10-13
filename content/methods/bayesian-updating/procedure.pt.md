## Purpose

Use este procedimento para atualizar a confiança em hipóteses concorrentes quando surgirem novas evidências e for possível declarar responsavelmente a base a priori e a direção da verossimilhança. Ele torna visíveis as taxas de base, a direção das evidências, a mudança a posteriori e a sensibilidade. Probabilidades exatas são opcionais; uma atualização ordinal é honesta quando as entradas numéricas não têm proveniência, mas uma probabilidade a posteriori precisa deve mostrar entradas e normalização.

## Use when

Use-o para sinais diagnósticos, interpretação de testes, evidências sequenciais, estimativas de risco e decisões em que uma nova observação deve modificar a confiança em hipóteses concorrentes. É adequado para perguntas sobre a probabilidade de uma hipótese após uma evidência, especialmente quando existe risco de negligenciar taxas de base.

## Do not use when

Não o use quando não houver base a priori defensável nem sequer uma direção ordinal da diferença das evidências entre hipóteses, ou quando a tarefa for aplicar uma regra estrita. Não confunda `P(E|H)` com `P(H|E)`, não reutilize a mesma evidência como atualizações independentes nem invente percentuais exatos para criar falsa certeza.

## Inputs to establish

Estabeleça hipóteses mutuamente exclusivas e suficientemente abrangentes, a decisão atual, a base a priori ou de taxas de base, novas evidências, direção ou valores de verossimilhança sob cada hipótese, dependências entre evidências e o limiar de ação. Faça no máximo duas perguntas decisivas quando uma base a priori ou definição de evidência ausente modificar a atualização; caso contrário, use uma base ordinal explicitamente rotulada.

## Procedure

1. Publique o conjunto de hipóteses concorrentes e o limiar de decisão. Declare o que está sendo atualizado e marque hipóteses como fornecidas pelo usuário, apoiadas por fonte ou provisórias; isso cria o estado visível da atualização.
2. Publique a base a priori de cada hipótese, incluindo fonte da taxa de base, população de referência ou base ordinal delimitada. Se as probabilidades a priori forem desconhecidas, mostre a incerteza sem escolher um número conveniente.
3. Publique cada evidência e sua direção sob todas as hipóteses: sustenta, enfraquece ou é predominantemente neutra. Verifique se os itens são independentes ou reutilizam parcialmente o mesmo sinal.
4. Publique a mudança a posteriori com aritmética exata apenas quando as entradas forem defensáveis; caso contrário, declare uma atualização qualitativa ou um intervalo. Mostre a normalização das hipóteses concorrentes e preserve a direção da mudança a priori para a posteriori.
5. Publique a sensibilidade aos pressupostos a priori e de verossimilhança. Identifique a mudança de valor ou direção que inverteria a classificação ou atravessaria o limiar de ação.
6. Publique a hipótese atualmente mais forte, o estado a posteriori e a próxima evidência que mais melhoraria a decisão. Mantenha visível uma hipótese plausível de posição inferior quando ainda for relevante.
7. Publique a conclusão atualizada e uma condição observável de reversão. Se faltar a base a priori ou a direção da verossimilhança, suspenda ou mantenha o resultado provisório, em vez de relatar uma probabilidade a posteriori inventada.

## Public output contract

Retorne `hypotheses`, `prior_basis`, `evidence_direction`, `posterior_change`, `normalization_or_update_range`, `sensitivity`, `decision_threshold` e `flip_condition`. O cartão deve distinguir uma probabilidade a posteriori calculada de uma atualização ordinal ou inferida. Os fundamentos usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**; uma taxa de base não é automaticamente verificada apenas por ser numérica.

## Evidence and uncertainty rules

A base a priori deve vir de uma taxa de base defensável, estimativa especializada com proveniência ou probabilidade a posteriori anterior. A verossimilhança é `P(E|H)`, não a probabilidade da hipótese após a evidência. Não atualize duas vezes com evidências dependentes. Se entradas confiáveis discordarem, mostre o conflito e reduza o suporte ou suspenda o resultado. Se a sensibilidade atravessar o limiar de ação, declare que a decisão é frágil.

## Stop conditions

Pare e faça uma pergunta bloqueante quando faltar o conjunto de hipóteses ou a definição da evidência e escolhas diferentes inverteriam a ação. Suspenda quando não existir base a priori defensável nem direção da verossimilhança, ou quando dependências impedirem uma atualização confiável. Pare quando a tarefa real for uma regra estrita, busca de explicações ou classificação da qualidade das fontes.

## Complement handoff

Encaminhe a `abduction` quando a tarefa principal não resolvida for gerar e comparar explicações, em vez de atualizar um conjunto definido de hipóteses. Transfira as evidências observadas, as hipóteses candidatas e o teste discriminante. O complemento não deve repetir o cálculo a posteriori.

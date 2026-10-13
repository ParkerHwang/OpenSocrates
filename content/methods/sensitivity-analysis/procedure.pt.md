## Purpose

Use este procedimento para testar como resultado de modelo, comparação ou decisão muda quando entradas ou pesos importantes variam em intervalos defensáveis. Identifique variáveis influentes, valores de troca, interações e suposições frágeis. Produza verificação transparente de robustez, não licença para intervalos dramáticos ou alegação de que modelo prova o futuro.

## Use when

Use quando já houver cálculo, modelo de previsão, justificativa de negócio, pontuação ou comparação e entradas incertas puderem mudar decisão. Ajuda a priorizar coleta, revelar limiar oculto e distinguir conclusão resistente a variação razoável da dependente de suposição estreita. Admite alterações numéricas ou ordinais com escala explícita.

## Do not use when

Não use sem modelo, comparação, regra decisória ou relação variável a perturbar. Não crie resultado de pergunta factual, referência indefinida ou intervalos sem proveniência. Não varie variáveis correlacionadas independentemente, suponha linearidade sem verificar ou reporte valor de troca mais preciso que as entradas permitem.

## Inputs to establish

Estabeleça modelo ou regra inicial, métrica de saída, limiar, entradas ou pesos, unidades e resultado atual. Defina intervalo plausível e proveniência por entrada incerta, incluindo dependências e restrições. Declare desenho da perturbação, arredondamento e teste individual, combinação estruturada ou comparação ordinal. Registre opção ou política informada. Faça no máximo duas perguntas decisivas, só se mudarem referência ou intervalo.

## Procedure

1. Publique fórmula ou regra inicial, entradas, unidades e resultado. **Resultado visível/mudança de estado:** partida reproduzível e limiar decisório nomeado.
2. Publique intervalos, pesos, dependências e evidência por intervalo. **Resultado visível/mudança de estado:** todo limite é verificado, calculado, inferido, assumido, não verificado ou conflitante, não escolhido por dramaticidade.
3. Execute testes individuais e depois apenas combinações estruturadas defensáveis. **Resultado visível/mudança de estado:** registre entrada alterada, saída, método, unidades e arredondamento; entradas correlacionadas mudam juntas quando necessário.
4. Publique direção, magnitude ou alteração ordinal, interações e valores de troca quando cruzar limiar. **Resultado visível/mudança de estado:** classifique influência, ausência de influência, robustez ou fragilidade sem alegar causalidade pela classificação.
5. Publique implicação decisória e prioridade de pesquisa das variáveis capazes de mudá-la. **Resultado visível/mudança de estado:** investigação ligada a condição de mudança nomeada, não maior variação bruta.
6. Publique conclusão robusta, frágil, provisória ou suspensa e próxima validação. **Resultado visível/mudança de estado:** referência, intervalo ou limiar ausente vira suspensão explícita, não sensibilidade fabricada.

## Public output contract

Retorne `baseline`, `tested_ranges`, `perturbation_results`, `switching_values`, `robust_or_fragile_conclusion`, `research_priority` e `flip_condition`, com estado sustentado, provisório ou suspenso. Declare limiar e entradas que o cruzam. Fundamentos da ficha identificam cálculos e entradas; incerteza nomeia limites de modelo ou intervalo; mudança é entrada ou limiar observável. Preserve registro completo e fórmulas no registro ou artefato.

## Evidence and uncertainty rules

Intervalos exigem fonte, restrição do usuário, observação histórica ou suposição explícita; conveniência não é evidência. Cálculos mostram fórmula, operandos, unidades e arredondamento. Preserve não linearidade, correlação, descontinuidade e incerteza da forma do modelo quando materiais. Com pesos apenas ordinais, reporte direção ou ordem dos limiares, não percentuais pseudoprecisos. Frequência de amostragem dos testes não implica probabilidade real. Resultado robusto pode produzir decisão frágil se limiar ou objetivo forem errados.

## Stop conditions

Faça uma pergunta bloqueadora e pare se referência, limiar ou saída alvo tiverem interpretações diferentes. Suspenda sem intervalo, dependência ou regra exigidos. Pare se nenhuma perturbação defensável mudar decisão ou restarem verificação de evidência, explicação causal ou compromisso entre opções mais amplo.

## Complement handoff

Encaminhe para `trade-off-analysis` se resultados precisarem de critérios, pesos e preferências das partes entre opções. Passe referência, valores de troca, robustez/fragilidade, proveniência dos intervalos e prioridades. Compare respeitando limites sem tratar classificação de sensibilidade como preferência ou probabilidade.

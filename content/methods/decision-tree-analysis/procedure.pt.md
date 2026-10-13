## Purpose

Use este procedimento para representar uma decisão que se desenrola no tempo: uma ação muda as possibilidades seguintes e eventos incertos levam a escolhas posteriores. Ele separa nós de decisão, acaso e resultado para rastrear a recomendação às informações. Pode usar avaliação retroativa aritmética com valores e probabilidades delimitados, mas deve suspender, sem fabricar precisão, quando os ramos não têm suporte.

## Use when

Use-o para lançamentos por etapas, escolhas entre piloto e escala, momento de manutenção ou substituição, opções de aguardar teste e outras decisões com ramos condicionais. É adequado quando ordem das ações importa, escolhas posteriores dependem de resultados observados e consequências têm valor apoiado por fonte ou descrição qualitativa claramente rotulada. Uma árvore ajuda quando a questão não é só qual opção pontua melhor agora, mas qual estratégia continua disponível após novas informações.

## Do not use when

Não o use para comparação estática sem sequência ou ramo de acaso significativo, fluxograma puramente mecânico ou regra vinculante sem escolha. Não desenhe ramos independentes para eventos de causa compartilhada ou dependentes de resultado anterior. Não calcule valor esperado se probabilidades, valores dos resultados ou ações condicionais não puderem ser delimitados. Se incerteza profunda e futuros externos coerentes importarem mais que aritmética dos ramos, encaminhe a scenario-planning.

## Inputs to establish

Declare ponto decisório, ações possíveis, momentos de observação, eventos de acaso, resultados finais, pontos de reversão e pessoa ou sistema que pode agir em cada nó. Registre proveniência das probabilidades, unidades dos resultados, temporalidade, custos, benefícios e dependências. Marque probabilidade como verificada, calculada de dados declarados, inferida, pressuposta, não verificada ou conflitante. Faça no máximo duas perguntas decisivas, como “Qual observação muda a próxima ação disponível?” e “Qual fonte delimita este ramo?”.

## Procedure

1. **Fixe a sequência.** Declare decisão, ordem das ações e observações, horizonte e pontos de reversão ou parada disponíveis. **Resultado visível/mudança de estado:** publique estrutura da árvore com cada nó conhecido rotulado decisão, acaso, observação ou resultado.
2. **Enumere ramos condicionais.** Liste ações ainda viáveis em cada nó decisório; em cada nó de acaso, resultados mutuamente exclusivos e o que habilitam depois. Preserve dependências, sem achatar tudo em ramos não relacionados. **Resultado visível/mudança de estado:** crie registro com campos de nó pai, filho, condição e próxima ação.
3. **Descreva resultados finais.** Dê a cada ramo final consequência, unidade, temporalidade, grupo afetado e estado das evidências. Mantenha restrições não comparáveis de segurança ou direitos fora do agregado. **Resultado visível/mudança de estado:** publique registro de resultados e marque valores ausentes ou conflitantes como suspensos ou não resolvidos.
4. **Delimite incerteza.** Associe fonte ou cálculo reproduzível a cada probabilidade; verifique completude dos ramos condicionais e compatibilidade com evento anterior. Sem probabilidade delimitável, use intervalo defensável ou ramo qualitativo apenas com base declarada, sem fingir resposta numérica. **Resultado visível/mudança de estado:** publique mapa de proveniência ou nota de suspensão para ramo não delimitado.
5. **Avalie retroativamente e teste robustez.** Começando pelos resultados finais, calcule ou compare ramos pais com valores e unidades declarados. Varie probabilidades ou resultados relevantes em intervalos defensáveis; mostre pior exposição, arrependimento ou limiar de reversão, sem depender de um só valor esperado. **Resultado visível/mudança de estado:** publique tabela retroativa com ação recomendada, condição de mudança e risco residual.
6. **Defina a estratégia.** Explique a ação sustentada agora, a observação que acionaria outra e onde pausar. Se um ramo não resolvido puder alterar a estratégia, suspenda a recomendação e nomeie a menor observação segura. **Resultado visível/mudança de estado:** publique nós, resumo de resultados, proveniência, ponto de reversão, incerteza e condição de reversão no Cartão de Conclusão.

## Public output contract

Retorne nós de decisão, acaso e resultado, ramos condicionais, consequências finais e ponto de reversão. Mostre proveniência de probabilidade em todo ramo numérico e unidades e expressões de valores calculados. Inclua exposição a risco, condição de mudança ou parada e próxima observação se a estratégia for provisória. A conclusão pública não deve sugerir que a árvore prova um resultado; aritmética detalhada e dependências ficam no registro de rastreabilidade.

## Evidence and uncertainty rules

Use verificado apenas para fonte identificável que sustenta ramo ou resultado, calculado para aritmética transparente de entradas declaradas, inferido para consequências de fundamentos rotulados, pressuposto para premissa explícita de planejamento, não verificado para entradas não checadas e conflitante para fontes confiáveis divergentes. Não invente taxa de base, probabilidade, utilidade, independência ou valor final. Se ramos não forem mutuamente exclusivos, revise antes de calcular. Trate intervalo numérico estreito sem proveniência como falsa precisão.

## Stop conditions

Suspenda se faltar sequência, próxima ação, resultado do ramo ou base probabilística de modo que possa mudar a estratégia. Suspenda se dependências não puderem ser representadas sem contagem dupla ou regra vinculante retirar a escolha. Se o espaço de ramos for aberto demais, declare observação ausente e encaminhe a scenario-planning, sem produzir valor esperado sem suporte.

## Complement handoff

Encaminhe a scenario-planning quando vários futuros externos coerentes, em vez de ramos de acaso delimitados, determinarem a preparação. Transfira apenas enquadramento decisório, incertezas relevantes, sinais dos ramos e ações sem arrependimento ou contingentes; exclua probabilidades sem suporte e deliberação privada.

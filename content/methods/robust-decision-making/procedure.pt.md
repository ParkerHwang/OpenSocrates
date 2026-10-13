## Purpose

Use este procedimento para escolher ação aceitável em vários futuros plausíveis quando nenhuma previsão única merece dominar a decisão. Torne visíveis incerteza, critérios de falha e compromissos, separando primeiro passo robusto de ações que devem esperar um sinal. Robusto não significa ótimo em todo futuro; significa superar o mínimo declarado sem distribuição de probabilidade inventada.

## Use when

Use para políticas, infraestrutura, investimentos, produtos ou operações duradouros expostos a incertezas interativas. Serve quando falhar custa caro, reverter é lento ou partes interessadas discordam da previsão. Responde ao que sobrevive a várias condições plausíveis, não ao resultado mais provável.

## Do not use when

Não use se um caso esperado for confiável e a escolha barata e totalmente reversível, ou se regra vinculante deixar uma única ação viável. Não catalogue piores casos arbitrários, declare ação superior em todos os futuros ou esconda o custo da robustez. Sem definição de sucesso e falha, esclareça decisão ou estabeleça critérios por método de evidência.

## Inputs to establish

Estabeleça decisão, ações viáveis, horizonte, partes interessadas e desempenho mínimo. Defina falha, arrependimento inaceitável e compromissos materiais antes dos testes. Liste incertezas profundas, dependências, restrições e poucos mundos plausíveis; não atribua probabilidades sem fonte defensável fornecida pelo usuário. Registre reversibilidade, custo, momento e compromissos atuais. Faça no máximo duas perguntas decisivas, só se mudarem opções ou mínimo aceitável.

## Procedure

1. Publique enquadramento, ações candidatas e critérios de aceitação. **Resultado visível/mudança de estado:** conjunto delimitado e mínimo explícito de aceitação/falha.
2. Publique registro de incertezas e mundos distintos internamente coerentes. **Resultado visível/mudança de estado:** uma previsão vira conjunto de teste visível; mundos contêm suposições e dependências, não probabilidades.
3. Teste toda ação em todo mundo pelos critérios declarados. **Resultado visível/mudança de estado:** matriz estratégia/mundo registra aceitável, frágil ou falho com rótulos de evidência.
4. Publique condições de falha, exposição ao arrependimento e grupos de mundos que pressionam a mesma ação. **Resultado visível/mudança de estado:** vulnerabilidades e compromissos nomeados, não ocultos em nota geral.
5. Publique ação robusta ou menor conjunto que supera o mínimo em todos os mundos testados. **Resultado visível/mudança de estado:** separe recomendação de custo, oportunidade perdida e vulnerabilidade residual.
6. Publique salvaguardas, primeiros passos reversíveis, ações contingentes e sinais com respostas aos gatilhos. **Resultado visível/mudança de estado:** decisão adaptativa, não aposta única no mundo preferido.
7. Publique estado sustentado, provisório ou suspenso e condição observável de mudança. **Resultado visível/mudança de estado:** critérios ou mundos decisivos ausentes produzem suspensão, não robustez alegada.

## Public output contract

Retorne `uncertainties`, `plausible_worlds`, `regret_or_failure_criteria`, `robust_action`, `tradeoffs`, `monitoring_signals`, `flip_condition` e estado sustentado, provisório ou suspenso. Explique superação do mínimo e fragilidades. A ficha declara uma conclusão, rotula fundamentos materiais, nomeia incerteza pendente e condição observável que mudaria ação; matrizes detalhadas ficam no registro ou artefato.

## Evidence and uncertainty rules

Mundos plausíveis são casos estruturados, não previsões nem amostra ponderada por probabilidade. Fundamente cada mundo material em observação, mecanismo defensável, restrição do usuário ou suposição explícita. Não invente frequências, perdas esperadas, utilidades ou robustez universal. Aceitável refere-se ao critério publicado. Marque cálculos com entradas e unidades; preserve conflito sem fazer média para ocultá-lo. Ação robusta pode ser pior em custo ou ganho potencial; mostre esse compromisso.

## Stop conditions

Faça uma pergunta bloqueadora e pare se opções ou desempenho mínimo admitirem interpretações materialmente diferentes. Suspenda sem incerteza decisiva, limiar de falha ou ação viável. Pare se houver previsão única confiável, regra sem margem ou trabalho restante de cenários, evidência ou comparação comum.

## Complement handoff

Encaminhe para `scenario-planning` se mundos precisarem de estrutura mais deliberada de futuros externos ou narrativa de sinais. Passe enquadramento, incertezas, mínimo, grupos vulneráveis e mundos atuais. Enriquecer mundos não deve esconder critérios de falha nem convertê-los em probabilidades.

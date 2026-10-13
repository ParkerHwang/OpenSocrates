## Purpose

Use este procedimento para substituir previsão interna por comparação externa baseada em classe defensável de casos concluídos e comparáveis. Estime o alvo por resultados observados e explicite fatos atuais que justificam ajustes. É apoio à calibração, não promessa nem licença para inventar população, distribuição ou probabilidade.

## Use when

Use para previsões de prazo, custo, demanda, adoção, confiabilidade ou entrega com casos anteriores semelhantes e plano interno possivelmente otimista. Ajuda quando se afirma que este caso é diferente sem mostrar como a diferença muda a faixa esperada. Serve a decisão que exige intervalo fundamentado, não estimativa pontual.

## Do not use when

Não use sem classe defensável de casos concluídos, com alvo ou unidade pouco claros, ou em caso único sem resultado comparável. Poucas histórias não constituem distribuição base; não selecione só sucessos nem transforme previsão interna em evidência. Se a tarefa for mecânica ou exigir diagnóstico causal em vez de calibração, pare e redirecione.

## Inputs to establish

Estabeleça resultado alvo, unidade, horizonte, data de corte e limite aceitável. Defina inclusão e exclusão antes de inspecionar resultados. Reúna casos observados, definições dos resultados, cobertura, ausências e fontes. Registre diferenças conhecidas do projeto atual e previsão interna. Faça no máximo duas perguntas decisivas, somente se mudarem classe ou alvo. Rotule entradas como verificadas, calculadas, inferidas, assumidas, não verificadas ou conflitantes.

## Procedure

1. Publique alvo, unidade, horizonte e limite decisório em uma frase. **Resultado visível/mudança de estado:** referência da previsão, com alvo ambíguo suspenso em vez de restringido silenciosamente.
2. Publique regra da classe, inclusão, exclusão, dimensões de semelhança e lacunas de cobertura. **Resultado visível/mudança de estado:** intuição torna-se definição auditável.
3. Publique distribuição dos resultados apenas dos casos disponíveis: contagem, centro, dispersão, intervalo e caudas quando calculáveis. **Resultado visível/mudança de estado:** cada estatística tem entradas e fonte/estado; indisponíveis seguem não verificadas.
4. Publique referência externa ao lado do plano interno e explique direção da diferença. **Resultado visível/mudança de estado:** registre plano dentro, acima ou abaixo da distribuição sem converter posição em probabilidade.
5. Publique ajustes de diferenças materiais atuais, uma de cada vez. **Resultado visível/mudança de estado:** cada ajuste traz direção, justificativa e estado; números só com escala defensável.
6. Publique intervalo delimitado e condições que tornam extremos plausíveis. **Resultado visível/mudança de estado:** amplie ou suspenda com cobertura, seleção ou caudas fracas, sem preencher lacuna com taxa base fabricada.
7. Publique estado sustentado, provisório ou suspenso, condição de mudança e próxima verificação. **Resultado visível/mudança de estado:** classe ou resultado decisivo ausente torna-se suspensão explícita, não recomendação arbitrária.

## Public output contract

Retorne `target`, `reference_class`, `base_distribution`, `adjustments`, `range`, `inside_view_comparison`, `flip_condition` e estado sustentado, provisório ou suspenso. Declare o que a classe observada sustenta, sem prometer que o caso atual a repetirá. Fundamentos usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**; incerteza nomeia cobertura ausente ou risco de seleção, e mudança deve ser observável, não se surgirem informações novas.

## Evidence and uncertainty rules

A classe só é sustentada por casos concluídos com alvo, unidade e inclusão definidos. Fonte pode verificar resultado sem verificar comparabilidade do projeto; marque comparação como inferida salvo apoio direto. Cálculos mostram casos ou referências e regra de arredondamento. Não invente mediana, cauda, amostra, taxa base ou probabilidade. Preserve viés de seleção, casos ausentes, definições conflitantes e limitações de amostra pequena. Dizer este caso é diferente continua hipótese de ajuste até haver evidência de direção e efeito.

## Stop conditions

Faça uma pergunta bloqueadora e pare quando alvo, unidade ou limite admitirem interpretações materialmente diferentes. Suspenda sem classe, definição de resultado ou entrada comparativa decisiva defensáveis. Pare quando o restante for explicação causal, escolha ou cálculo mecânico; encaminhe sem forçar previsão externa.

## Complement handoff

Encaminhe para `sensitivity-analysis` se mudanças da distribuição ou ajustes atuais determinarem escolha. Passe alvo, referência observada, intervalos de ajuste testados, limites de cobertura e condição de troca. Perturbe entradas sem reconstruir classe nem chamar resultado de nova taxa base.

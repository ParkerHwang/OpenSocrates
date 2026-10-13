## Purpose

Use este procedimento para decompor uma questão ampla de diagnóstico, planejamento ou cobertura em uma hierarquia com ramos mutuamente claros, coletivamente adequados e folhas acionáveis. Selecione um eixo de decomposição por nível, separe árvores de por quê e como e associe verificação ou próxima ação a cada ramo terminal. A árvore estrutura a busca; não prova a verdade de todos os ramos.

## Use when

Use quando o problema for amplo, as causas forem pouco claras, o plano precisar de cobertura ou uma pergunta de por quê, como ou o quê exigir estrutura exaustiva. Serve a diagnóstico, riscos, requisitos e exploração de soluções em que sobreposição causaria responsabilidade duplicada ou trabalho omitido.

## Do not use when

Não use se um ciclo de retroalimentação fortemente acoplado não puder ser representado responsavelmente como hierarquia, ou se bastarem lista simples ou cálculo direto. Não misture causas e soluções no mesmo nível, esconda lacuna material em outros nem continue subdividindo quando a próxima ação já estiver clara.

## Inputs to establish

Estabeleça pergunta raiz, tipo (`why`, `how` ou `what`), medida de sucesso, escopo, fatos conhecidos e verificações disponíveis. Escolha o eixo do primeiro nível e registre a adequação. Faça no máximo uma pergunta decisiva se a raiz ou o tipo mudar a análise; caso contrário, declare uma raiz delimitada.

## Procedure

1. Publique uma pergunta raiz mensurável e o tipo escolhido. Declare escopo e medida de sucesso para estabelecer a referência visível da árvore.
2. Publique ramos do primeiro nível usando um único eixo e rotule-o. Registre se cada ramo foi observado, inferido ou é candidato a verificar.
3. Publique nível adicional somente quando uma divisão mais fina mudar ação ou teste. Em cada nível, mostre separadamente exclusão mútua e cobertura como atualização do estado.
4. Publique folhas com um método de verificação, pedido de dados, responsável ou próxima ação para cada uma. Uma folha abstrata não é terminal; mantenha a árvore aberta ou reduza a raiz.
5. Publique ramos podados e justificativas, como evidência contraditória, exclusão de escopo ou cobertura duplicada. Não elimine ramos só por conveniência.
6. Publique ordem de prioridade por materialidade, evidência e possibilidade de ação, sem precisão numérica inventada. Marque ramos que exijam método causal ou de evidência separado.
7. Publique árvore concluída, lacunas de cobertura e condição observável de mudança. Se um ramo crítico não for testável nem delimitável, suspenda o julgamento ou faça uma pergunta bloqueadora.

## Public output contract

Retorne `root_question`, `tree_type`, `decomposition_axis`, `mutually_clear_branches`, `branches`, `leaf_tests`, `leaves_with_tests`, `pruned_branches_and_reasons`, `coverage_gaps`, `priority_order` e `flip_condition`. O resultado público mostra ramos mutuamente claros, cobertura coletivamente relevante e folhas executáveis. Os fundamentos da ficha usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**. Não apresente a própria árvore como prova de causalidade.

## Evidence and uncertainty rules

ME e CE são verificações separadas: ausência de sobreposição não implica cobertura, nem cobertura implica ausência de sobreposição. Uma fórmula conhecida é estrutura candidata até suas suposições corresponderem ao domínio. Identifique evidência ou teste de cada folha; ramos sem sustentação continuam hipóteses. Se houver conflito entre ramos ou lacuna que possa mudar a decisão, revele-a e suspenda ou reduza a força da conclusão.

## Stop conditions

Pare e faça uma pergunta bloqueadora se raiz ou tipo não puderem ser delimitados e alternativas conduzirem a trabalhos diferentes. Suspenda se uma lacuna material não tiver teste ou se a interdependência tornar a hierarquia enganosa. Pare quando as folhas tiverem ações claras e o restante pertencer a método causal, de evidência ou decisão.

## Complement handoff

Encaminhe para `root-cause-analysis` quando o ramo selecionado tratar de falha recorrente e exigir cadeia causal em vez de mais decomposição. Passe raiz, ramo selecionado, lacunas de evidência e testes das folhas. O complemento não reconstrói ramos não relacionados.

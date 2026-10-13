## Purpose

Use este procedimento para tornar visíveis as crenças que sustentam uma ideia, separar importância de evidência e selecionar o menor teste seguro para pressupostos capazes de alterar a decisão. Ele produz uma base de aprendizagem priorizada, não um veredito de verdade.

## Use when

Use-o antes de assumir um compromisso com uma ideia de produto, mudança operacional, direção de pesquisa ou julgamento dependente de crenças incertas. É útil quando uma equipe não concorda sobre o que precisa ser verdadeiro, quando as evidências são desiguais ou quando os testes possíveis precisam de uma ordem explícita. É especialmente útil antes de um experimento reversível ou compromisso de recursos, enquanto a decisão ainda pode mudar com segurança.

## Do not use when

Não o use para um pedido mecânico, uma regra vinculante sem margem de escolha ou uma decisão irreversível. Não exponha pressupostos privados ou sensíveis apenas para completar um mapa; limite o resultado às informações autorizadas. Não invente um teste quando nenhum resultado observável puder distinguir o pressuposto, ou quando o teste criar exposição jurídica, de segurança, de privacidade ou operacional relevante. Se o trabalho for um experimento de mercado, encaminhe o pressuposto selecionado a `lean-startup`, sem transformar este mapa em um relatório completo.

## Inputs to establish

Estabeleça a pergunta de decisão, o resultado desejado, a ação proposta e o que alteraria materialmente a decisão. Reúna pressupostos candidatos como afirmações testáveis e classifique-os como desejabilidade, viabilidade econômica, viabilidade de execução ou outro domínio nomeado. Registre a fonte, a observação do usuário, o cálculo ou a inferência de cada um. Defina as menores opções de teste seguro, as restrições, o responsável, a janela de observação e a regra de decisão. Faça no máximo duas perguntas concisas, apenas quando a resposta ausente puder mudar o conjunto mais arriscado ou a segurança do teste; caso contrário, marque o item como pressuposto.

## Procedure

1. **Publique o enquadramento.** Declare a pergunta de decisão, o resultado pretendido, o escopo e os limites da decisão em um registro compacto. Marque cada limite como fornecido pelo usuário, verificado em fonte, inferido ou pressuposto. **Resultado visível/mudança de estado:** estado de enquadramento.
2. **Publique o registro de pressupostos.** Reescreva cada crença como uma afirmação que uma observação poderia sustentar, enfraquecer ou deixar sem solução. Associe seu domínio e a consequência de ser falsa. **Resultado visível/mudança de estado:** registro rotulado de pressupostos.
3. **Publique os dois eixos.** Posicione cada pressuposto em um eixo ordinal de importância e em um eixo de estado das evidências. Use alta, média ou baixa apenas com uma base declarada, e `verified`, `computed`, `inferred`, `assumed`, `unverified` ou `conflicted` para o suporte. **Resultado visível/mudança de estado:** mapa de importância/evidência.
4. **Publique o conjunto mais arriscado.** Selecione pressupostos cuja falha modificaria materialmente o resultado e cujo suporte seja mais fraco ou conflitante. Explique cada seleção, preserve empates indistinguíveis e registre incertezas não resolvidas. **Resultado visível/mudança de estado:** conjunto mais arriscado e incerteza.
5. **Publique um cartão de teste seguro.** Para cada pressuposto selecionado, nomeie o teste reversível de menor custo, o sinal observável, a janela de observação, o responsável e a regra de decisão. Inclua um limite de parada ou reversão. **Resultado visível/mudança de estado:** cartão de teste seguro ou suspensão.
6. **Publique o mapa de decisão.** Declare o que um sinal favorável, contrário, conflitante ou ausente mudaria: continuar, revisar, buscar evidências ou suspender. **Resultado visível/mudança de estado:** conclusão provisória e condições de reversão.

## Public output contract

Retorne os campos prontos para cartão `assumptions`, `importance_evidence_axes`, `riskiest_set`, `next_test` e `flip_condition`. Cada pressuposto deve manter seu domínio, consequência e estado das evidências. `next_test` deve conter um sinal observável, um limite seguro e uma regra de decisão; não deve prometer provar a ideia inteira. Inclua no máximo três pressupostos relevantes e duas incertezas não resolvidas no resultado resumido, deixando outros ramos no registro de rastreabilidade. Se faltar um pressuposto decisivo ou um limite do teste, declare o resultado suspenso ou provisório.

## Evidence and uncertainty rules

Um pressuposto não é fato porque é repetido, importante ou plausível. Vincule alegações `verified` a uma fonte de apoio quando disponível; mostre entradas de alegações `computed`; rotule raciocínio a partir de outros fundamentos como `inferred`, premissas adotadas como `assumed`, a verificação ausente como `unverified` e divergências como `conflicted`. Use importância ordinal apenas com a consequência ou dependência decisória declarada. Não invente probabilidades, tamanhos de amostra nem resultados de testes. Um sinal atualiza o pressuposto apenas no contexto testado; não permite generalizar sem mais suporte.

## Stop conditions

Suspenda quando faltar a pergunta de decisão, a consequência relevante ou autorização para expor um pressuposto. Suspenda quando dois pressupostos permanecerem empatados e a evidência ausente puder alterar a ordem dos testes. Pare antes de propor um teste se a exposição for insegura, ilegal, irreversível ou não significativamente observável. Se a tarefa for mecânica ou não houver margem de escolha, interrompa este método e encaminhe à resposta direta ou normativa aplicável. Não transforme um mapa vazio em recomendação.

## Complement handoff

Encaminhe a `lean-startup` quando o pressuposto mais arriscado publicado for uma hipótese de mercado, produto, valor, crescimento ou receita que exige um experimento mínimo de aprendizagem. Transfira apenas a afirmação, o domínio, a consequência, o estado das evidências, o sinal seguro selecionado e a regra de decisão. Não repita todo o mapa nem sugira que o complemento já executou o teste. Use `value-of-information` separadamente quando a questão aberta for principalmente se pesquisa adicional compensa seu custo.

## Purpose

Use este procedimento para testar se regra, custo, fluxo ou arquitetura familiar é realmente necessário ou apenas herdado. Decomponha o problema em alegações e restrições, verifique cada uma e reconstrua uma opção a partir das restrições que sobreviverem. Ele protege contra imitação cega e redução imprudente: restrição não é descartada por inconveniência e possibilidade física não vira automaticamente plano viável.

## Use when

Use-o quando “é assim que se faz”, convenção setorial, dependência histórica ou estrutura de custos pressuposta impedir reformulação de grande efeito. Serve para preços, arquitetura de produto, processos, alocação de recursos e requisitos quando o usuário quer questionar a base da escolha existente. Ajuda quando opções esgotadas parecem herdar pressupostos que já não se aplicam.

## Do not use when

Não o use para procedimento padrão validado que basta executar, ou quando regra vinculante, restrição de segurança, obrigação jurídica ou interface externa fixa não puder ser descartada. Não trate preferência, orçamento, prazo ou coordenação social como fatos puramente físicos. Não prometa reformulação a partir de pressupostos não verificados nem omita restrições de implementação após decompor.

## Inputs to establish

Estabeleça resultado-alvo, abordagem atual, requisitos declarados, restrições, recursos, dependências e razão de acreditar que a abordagem é necessária. Separe restrições rígidas, negociáveis, convenções e desconhecidos. Faça no máximo duas perguntas decisivas, apenas se mudarem a reconstrução. Identifique regras de alto impacto que devem permanecer vigentes.

## Procedure

1. Publique resultado-alvo e abordagem atual em uma frase, limites e medida de sucesso. Isso cria referência visível para comparar à opção reconstruída.
2. Publique decomposição em requisitos atômicos, dependências e restrições alegadas. Marque itens fornecidos pelo usuário, apoiados por fonte, inferidos ou pressupostos; mude estado de “dado” para “a verificar”.
3. Publique veredito de necessidade de cada restrição: física ou logicamente necessária, externamente vinculante, contingente, baseada em preferência ou não verificada. Associe teste ou fonte de apoio.
4. Publique conjunto sobrevivente e retire apenas pressupostos reprovados na verificação. Se um item contestado afetar materialmente segurança, legalidade ou viabilidade, preserve-o como restrição explícita não resolvida, sem retirar silenciosamente.
5. Publique reconstrução baseada nas restrições sobreviventes. Declare implicações de recursos, tempo, dependências e coordenação, para que seja mais que fisicamente imaginável.
6. Publique diferença da abordagem convencional: o que muda, qual pressuposto permitiu a mudança e qual novo risco ou compromisso surge. Acrescente pequena validação para cada requisito não verificado.
7. Publique requisitos derivados, opção reconstruída e condição observável de reversão. Se faltar restrição irredutível ou entrada decisiva, use conclusão provisória ou suspensa, sem alegar descoberta revolucionária.

## Public output contract

Retorne `irreducible_constraints`, `derived_requirements`, `reconstructed_option`, `assumptions_reintroduced`, `reintroduced_assumptions`, `conventional_delta`, `new_risks` e `flip_condition`. A primeira linha declara reformulação sustentada, provisória ou suspensa. Distinga opção fisicamente possível daquela que atende custo, tempo, segurança e governança do usuário. Fundamentos do cartão usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**; não apresente convenção sem rótulo como evidência.

## Evidence and uncertainty rules

“Necessário” exige base lógica, física, contratual, de segurança ou outra nomeada; inconveniência não prova necessidade. Fonte sobre prática comum sustenta prevalência, não inevitabilidade. Cálculos devem declarar entradas e unidades. Se reconstrução depender de vínculo não verificado, pode ser hipótese delimitada, não recomendação fortemente sustentada. Preserve conflitos sem calcular média de restrições incompatíveis.

## Stop conditions

Pare e faça pergunta bloqueante se resultado-alvo ou limites inegociáveis de segurança/legalidade não forem claros e respostas distintas gerarem reconstruções distintas. Suspenda se restrição irredutível ou entrada obrigatória não puder ser estabelecida. Pare quando todas as restrições relevantes forem externamente fixas ou restar comparação comum de opções, verificação de evidências ou implementação.

## Complement handoff

Encaminhe a `morphological-analysis` quando requisitos sobreviventes puderem variar em dimensões coerentes e a próxima tarefa for explorar combinações. Transfira requisitos derivados, restrições preservadas e exclusões de viabilidade. O complemento não deve repetir decomposição nem rediscutir pressupostos retirados.

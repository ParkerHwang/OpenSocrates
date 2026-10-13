## Purpose

Use este procedimento para tornar visíveis os limites de um julgamento. Ele identifica quem e o que o enquadramento atual inclui, quem é afetado mas excluído e como mudar os limites modifica a conclusão. O objetivo não é produzir uma lista maior de partes interessadas, mas revelar os pressupostos de responsabilidade, benefício, custo, autoridade, horizonte temporal, jurisdição e limites do sistema que fazem a resposta atual parecer inevitável. Separe alegações descritivas, sobre o que acontece, das normativas, sobre o que deve contar ou ser feito.

## Use when

Use-o quando uma resposta puder mudar conforme os atores considerados, os resultados medidos, a geografia ou o período incluído, o responsável pela decisão ou as externalidades consideradas fora de escopo. É especialmente útil em questões de política, produto, organização, interesse público e mudança de sistemas, quando uma resposta tecnicamente correta para um grupo pode impor custos a outro. Uma comparação delimitada pode usá-lo quando a própria comparação oculta uma população ou um horizonte temporal omitido.

## Do not use when

Não o use quando escopo, responsável, população afetada, jurisdição e horizonte temporal já forem explícitos e restar apenas comparar opções ou verificar uma fonte. Não transforme um pedido puramente mecânico em um exercício de limites. Não infira um grupo afetado apenas porque é imaginável; marque-o como hipótese até que a tarefa ou as evidências tornem a conexão relevante.

## Inputs to establish

Estabeleça a pergunta de decisão, o responsável, os beneficiários pretendidos, a regra atual de inclusão, o horizonte temporal, a geografia ou jurisdição, os recursos contabilizados e a medida de resultado. Nomeie até três fatos ausentes que poderiam alterar materialmente os limites. Se o usuário não os forneceu, declare limites provisórios razoáveis e faça no máximo uma pergunta concisa, apenas quando respostas diferentes mudariam a recomendação. Distinga fatos fornecidos pelo usuário, fontes verificadas, efeitos inferidos e escolhas de valor.

## Procedure

1. Publique a pergunta de decisão em uma frase e os limites provisórios: quem, o quê, onde, quando e para qual resultado. Declare se foram fornecidos pelo usuário ou pressupostos; isso cria o estado visível de enquadramento.
2. Publique um registro do conjunto incluído, com atores, propósitos, conhecimento, recursos e direitos decisórios. Associe uma razão breve a cada inclusão para que os limites sejam auditáveis, não apenas afirmados.
3. Publique um registro dos excluídos mas afetados. Separe efeitos diretos, indiretos e pessoas que poderiam questionar o enquadramento; marque entradas incertas como hipóteses, não fatos.
4. Publique a separação fato/valor: liste observações descritivas separadamente dos julgamentos sobre quais benefícios, custos, vozes ou direitos devem contar. Essa mudança evita apresentar uma escolha de valor como limite neutro do sistema.
5. Publique uma comparação de benefícios e custos entre grupos incluídos e omitidos, usando apenas efeitos relevantes. Registre um rótulo de evidência para cada efeito e marque efeitos não verificados como não resolvidos.
6. Publique uma ou mais variantes dos limites, como horizonte temporal mais amplo, outra jurisdição ou um grupo afetado adicional. Para cada variante, declare se mudam a conclusão, a ordem das opções, o risco ou o critério de conclusão da tarefa.
7. Publique os limites atuais, a consequência da mudança mais relevante para a decisão e uma condição observável de reversão. Se faltar um fato decisivo dos limites, torne a conclusão provisória ou suspensa, sem preencher a lacuna com especulação.

## Public output contract

Retorne um resultado compacto, pronto para cartão, com `current_boundary`, `omitted_boundary`, `benefit_and_cost_effects`, `boundary_variant`, `consequence_of_changing_it` e `flip_condition`. A primeira linha declara os limites atuais e se sustentam, enfraquecem ou suspendem o julgamento. Inclua no máximo três pressupostos relevantes e duas incertezas não resolvidas. Os fundamentos usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**; as alternativas resumem variantes relevantes, sem listar todas as partes interessadas.

## Evidence and uncertainty rules

Um grupo afetado não é, por si só, evidência de um efeito. Use uma fonte, documento fornecido pelo usuário, cálculo reproduzível ou inferência claramente rotulada para cada benefício ou custo relevante. Não trate a opinião majoritária ou a preferência do responsável como prova de que um grupo omitido é irrelevante. Se variantes produzirem conclusões incompatíveis, rotule o julgamento **conflicted** ou **held** até que o responsável autorizado escolha o escopo aplicável. Um fato decisivo ausente só sustenta uma conclusão provisória.

## Stop conditions

Pare e faça uma pergunta bloqueante quando dois limites plausíveis levarem a ações materialmente diferentes e não for possível escolher com segurança pelo propósito do usuário ou por uma regra autorizada. Suspenda quando um grupo afetado, jurisdição ou horizonte temporal for decisivo mas não puder ser identificado. Interrompa o método quando os limites forem explícitos e não restar ator ou limite relevante omitido; encaminhe ao método da comparação ou evidência real.

## Complement handoff

Encaminhe a `stakeholder-analysis` apenas como complemento focado quando a revisão revelar questões relevantes de poder, consentimento, implementação ou conflito. Transfira os conjuntos incluído/omitido publicados, a variante selecionada e o efeito não resolvido que exige essa análise. Não ative um segundo procedimento completo nem repita o inventário de limites.

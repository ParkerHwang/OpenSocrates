## Purpose

Use este procedimento para transformar alegação, explicação ou plano favorito em previsão arriscada e testável e especificar o que contaria contra ele. Ele separa alegação-alvo, pressupostos auxiliares e falha de medição, depois relata o que o teste observado pode e não pode estabelecer. Uma previsão fracassada é evidência contra a configuração testada, não refutação automática de todas as ideias relacionadas.

## Use when

Use-o quando uma alegação deve gerar previsão arriscada, o usuário pergunta o que poderia provar uma explicação errada ou narrativas posteriores são confundidas com previsões. Serve para hipóteses de pesquisa, planos de produto, explicações diagnósticas e alegações fortes que precisam de tentativa decisiva de refutação.

## Do not use when

Não o use sem implicação testável declarada, para escolha de valores, execução puramente mecânica ou alegação que seja apenas definição. Não trate testabilidade como prova, salve toda previsão fracassada com pressuposto auxiliar ad hoc nem descarte teoria complexa após uma falha sem verificar medição e configuração auxiliar.

## Inputs to establish

Estabeleça alegação-alvo, escopo, previsão arriscada, janela de observação, medição, pressupostos auxiliares, limiar de refutação e decisão afetada. Declare teste planejado, observado ou indisponível. Faça no máximo uma pergunta decisiva quando previsão ou limiar não puderem ser delimitados de outro modo.

## Procedure

1. Publique alegação e escopo e reescreva-a como previsão arriscada que possa falhar. Isso cria alvo visível de teste, não explicação posterior.
2. Publique o refutador: resultado, limiar ou padrão observável que contaria contra a alegação. Exclua condições vagas como “evidência inesperada”.
3. Publique pressupostos auxiliares e condições de medição separados da alegação-alvo. Marque qual falha implicaria alegação, configuração ou medição.
4. Publique teste planejado ou observado, proveniência e resultado. Se indisponível, declare observação necessária e mantenha estado não verificado.
5. Publique interpretação: sustentada neste teste, enfraquecida, ainda não testada ou inconclusiva. Não transforme resultado não refutador em confirmação forte.
6. Publique reparos propostos e verifique se foram especificados antes do resultado ou acrescentados ad hoc. Reparo que imuniza alegação sem suporte independente continua fraqueza.
7. Publique estado atual, próximo teste e condição observável de reversão. Se nenhum refutador puder ser declarado, suspenda ou recuse o método, sem fabricar linguagem de aparência científica.

## Public output contract

Retorne `claim`, `scope`, `risky_prediction`, `falsifier`, `auxiliary_assumptions`, `measurement_conditions`, `observed_needed_test`, `test_and_provenance`, `observed_or_needed_result`, `status` e `flip_condition`. Distinga não testado, inconclusivo, enfraquecido e sustentado neste teste. Os fundamentos usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**; alegação não refutada não é automaticamente verificada.

## Evidence and uncertainty rules

Um refutador deve ser observável e ligado a escopo preespecificado. Um teste fracassado pode questionar pressuposto auxiliar ou medição, não a teoria inteira. Não conte ajuste posterior como suporte independente. Se o teste não foi executado ou o limiar foi escolhido após ver o resultado, rotule conclusão não verificada ou conflitante e declare a limitação.

## Stop conditions

Pare e faça uma pergunta bloqueante quando alegação ou previsão não puderem ser delimitadas. Recuse ou suspenda se não houver implicação testável, a observação necessária estiver indisponível ou alegação de alto impacto não tiver teste seguro. Pare se a tarefa for qualidade de fontes, implicação formal ou gerar explicações, não tentativa de refutação.

## Complement handoff

Encaminhe a `lean-startup` apenas quando a alegação refutável for hipótese de produto ou mercado e teste mínimo seguro for a próxima decisão. Transfira previsão arriscada, refutador, condições de medição e exclusões de segurança. O complemento não deve substituir refutador ausente por experimento genérico.

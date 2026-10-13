## Purpose

Use este procedimento para conclusões que normalmente decorrem de uma regra, mas podem ser retiradas diante de exceções ou novas evidências. Ele declara uma regra padrão, aplica-a provisoriamente, distingue refutadores da conclusão de enfraquecedores do vínculo e registra condições explícitas de retirada. O resultado é julgamento provisório controlado, não maneira enfraquecida de declarar regra incondicional.

## Use when

Use-o em direito, políticas, saúde, operações, regras de senso comum e outros domínios em que generalizações admitem exceções ou evidências chegam com o tempo. É adequado a raciocínio “normalmente”, “salvo se” e “prima facie”, e a julgamentos que precisam ser revisáveis sem se tornarem arbitrários.

## Do not use when

Não o use quando regra estrita e premissas estabelecidas implicarem o resultado, ou se a questão for apenas classificar fontes ou atualizar estatísticas. Não liste toda exceção imaginável, trate problema de credibilidade como contradição direta nem prefira a afirmação mais recente apenas pela recência. Não afirme que ausência de refutador conhecido prova a conclusão.

## Inputs to establish

Estabeleça regra padrão, fatos acionadores, escopo da regra, exceções conhecidas, possíveis refutadores da conclusão e do vínculo e decisão afetada. Identifique regra mais específica que poderia ter precedência. Faça no máximo duas perguntas decisivas quando regra ou fato acionador não forem claros; caso contrário, marque a premissa provisória.

## Procedure

1. Publique a regra padrão delimitada, como “normalmente P implica Q”, com fonte, escopo e estado das evidências. Isso cria o estado visível da regra.
2. Publique fatos aplicáveis e conclusão prima facie. Rotule-a provisória e declare as condições de aplicação da regra padrão.
3. Publique separadamente refutadores que sustentam não-Q e enfraquecedores que reduzem o apoio da ligação P-Q. Registre cada um como verificado, alegado ou desconhecido.
4. Publique regras concorrentes e aplique especificidade quando uma regra for realmente subconjunto de outra. Se não resolver o conflito, defina estado conflitante ou suspenso, sem usar recência ou tom de confiança.
5. Publique condições explícitas de retirada: fato observável que faria retirar Q, enfraquecer a justificativa ou exigir novo julgamento. Mantenha a condição mais precisa que “surge informação nova”.
6. Publique o estado atualizado após refutadores conhecidos: provisório, sustentado, retirado, conflitante ou suspenso. Declare se mudou por refutação da conclusão, enfraquecimento do vínculo ou conflito não resolvido.
7. Publique conclusão atual, refutadores aplicáveis e condição de reversão. Se faltar fato acionador ou exceção decisiva, suspenda ou mantenha provisório, sem elevar à certeza.

## Public output contract

Retorne `default_rule`, `applicable_facts`, `prima_facie_conclusion`, `exceptions_defeaters`, `rebutting_defeaters`, `undercutting_defeaters`, `specificity_resolution`, `withdrawal_conditions`, `current_status` e `flip_condition`. O cartão deve tornar visíveis provisoriedade e refutadores relevantes. Fundamentos usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**; nunca chame a conclusão padrão de incondicional.

## Evidence and uncertainty rules

Um refutador da conclusão conflita com ela; um enfraquecedor do vínculo reduz a razão de os fatos a sustentarem sem provar o oposto. Especificidade é prioridade estrutural, não regra de recência. Verifique escopo e independência de novas evidências antes de mudar o estado. Se um refutador relevante não estiver resolvido, reduza o apoio ou suspenda e declare a verificação necessária.

## Stop conditions

Pare e faça uma pergunta bloqueante quando regra padrão ou fatos acionadores não puderem ser identificados e regras concorrentes levarem a ações diferentes. Suspenda quando faltar exceção, fonte ou condição decisiva de aplicabilidade. Pare quando a regra for estrita sem exceções ou a tarefa restante for atualizar evidência probabilística.

## Complement handoff

Encaminhe a `premortem-analysis` quando a regra provisória sustentar um plano escolhido e a preocupação restante for como ele pode falhar. Transfira conclusão padrão, refutadores conhecidos e condições de retirada. O complemento não deve reclassificar refutadores nem repetir o inventário de regras.

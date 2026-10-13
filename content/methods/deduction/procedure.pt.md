## Purpose

Use este procedimento para determinar se uma conclusão decorre necessariamente de premissas explícitas e uma regra, separando validade da verdade das premissas. Ele padroniza o argumento, revela premissas ocultas, verifica a forma e identifica a premissa cuja falha invalidaria a conclusão. Uma forma válida não torna, por si só, sólido um argumento sobre o mundo real.

## Use when

Use-o para aplicar regras, verificar argumentos formais, interpretar contratos ou políticas e examinar alegações de que um resultado deve decorrer de condições declaradas. É adequado quando as premissas relevantes podem ser explicitadas e a questão é implicação necessária, não generalização empírica.

## Do not use when

Não o use quando as premissas são incertas e a tarefa real é estimar, diagnosticar, generalizar ou atualizar confiança. Não trate uma premissa provável como provada, confunda `P(E|H)` com implicação necessária nem chame uma forma inválida de válida porque sua conclusão por acaso é verdadeira. Não invente uma regra não fornecida pelo usuário ou pela fonte aplicável.

## Inputs to establish

Estabeleça conclusão proposta, premissas, regra ou implicação aplicável, escopo, definições e fonte de cada premissa. Marque explicitamente premissas ocultas e identifique se a tarefa exige validade, solidez ou apenas resultado condicional. Faça no máximo uma pergunta decisiva quando uma regra ou premissa ausente mudar a forma; caso contrário, declare o pressuposto condicional.

## Procedure

1. Publique a conclusão e padronize o argumento em premissas numeradas, regra e conclusão. Marque premissas ocultas como `[implicit]`; isso cria o estado visível de formalização.
2. Publique a forma argumentativa, como modus ponens, modus tollens, silogismo válido, afirmação do consequente ou negação do antecedente. Se nenhuma forma reconhecida corresponder, mostre a relação estrutural relevante sem forçar um rótulo.
3. Publique o veredito de validade: supondo verdadeiras as premissas, a conclusão necessariamente é verdadeira? Declare o padrão de contraexemplo quando a forma for inválida.
4. Publique tabela de estado das premissas com fonte, escopo e estado das evidências para cada premissa e regra. Separe forma válida de argumento sólido; isso é uma atualização visível do julgamento.
5. Publique a premissa ou condição da regra que invalida. Declare exatamente o que quebraria a implicação e distinga exceção à regra de premissa falsa.
6. Publique a conclusão como sólida, válida mas não sólida, inválida ou condicional, com a menor verificação ausente. Não eleve seu estado porque a conclusão parece plausível.
7. Publique a conclusão atual e uma condição observável de reversão. Se faltar premissa ou regra decisiva, suspenda a alegação sobre o mundo real, preservando a implicação condicional.

## Public output contract

Retorne `premises`, `hidden_premises`, `rule`, `rule_or_form`, `conclusion`, `validity_verdict`, `premise_status`, `invalidating_premise`, `soundness_verdict` e `flip_condition`. O resultado deve declarar se a forma é válida e se as premissas têm suporte; não deve fundir ambos em um único rótulo de confiança. Os fundamentos usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**.

## Evidence and uncertainty rules

Validade é uma relação estrutural e não verifica premissas. Uma fonte pode sustentar uma premissa sem provar que a regra se aplica a este escopo. Premissas ocultas continuam pressupostos até terem suporte. Se uma premissa for contestada, preserve o resultado condicional e reduza o apoio ou suspenda a conclusão aplicada. Não use uma única conclusão verdadeira para validar uma inferência inválida.

## Stop conditions

Pare e faça uma pergunta bloqueante quando faltar regra aplicável ou conclusão e formas possíveis levarem a resultados diferentes. Suspenda quando uma premissa relevante não puder ser verificada, relatando a implicação condicional válida se existir. Pare quando a tarefa for probabilística, causal ou comparativa, não de implicação necessária.

## Complement handoff

Encaminhe a `conceptual-analysis` quando a disputa formal depender de termo ambíguo ou definição de escopo. Transfira premissas padronizadas, termo contestado e regra afetada. O complemento deve esclarecer o conceito sem refazer o veredito de validade.

## Purpose

Use este procedimento para escolher um modo de resposta a partir da forma observada de uma situação. Ele distingue padrões repetíveis de causa e efeito de situações que exigem análise especializada, experimentos seguros, contenção urgente ou melhor enquadramento. Não serve para enfeitar uma recomendação com um rótulo de domínio, mas para tornar visíveis evidências de classificação, ação decorrente e sinal que poderia mudar a classificação.

## Use when

Use-o quando a resposta proposta puder não corresponder à situação: equipe aplica processo fixo a problema adaptativo, aguarda análise durante perturbação rápida ou trata vários problemas distintos como um só. É útil quando escolher entre padronizar, analisar, sondar e agir é a própria decisão. Também pode separar uma situação mista em partes que exigem respostas diferentes.

## Do not use when

Não o use para tarefa puramente mecânica, regra estabelecida sem escolha significativa ou pedido que só exige cálculo conhecido ou transcrição. Não force classificação quando o usuário quer rótulo decorativo, sem mudança de ação. Não trate contexto complexo como automaticamente mais importante nem claro como automaticamente seguro; a classificação descreve a relação decisória, não a gravidade das consequências.

## Inputs to establish

Estabeleça pergunta de decisão, limites da situação, horizonte temporal, padrão observado e restrições imediatas de segurança ou continuidade. Reúna observações, exemplos anteriores, conhecimento especializado e fatos do usuário, marcando o verificado, inferido, pressuposto e ainda não verificado. Faça no máximo duas perguntas concisas, apenas se a resposta puder mudar o modo de ação. Se a observação decisiva estiver indisponível, declare limites provisórios e prossiga apenas até uma suspensão claramente marcada.

## Procedure

1. Publique em uma frase pergunta de decisão, escopo, horizonte temporal e restrição imediata. Marque cada elemento como fornecido pelo usuário ou pressuposto. Resultado visível/mudança de estado: enquadramento publicado.
2. Publique registro de observações causais que separe relações repetíveis, dependentes de especialistas, retroalimentação emergente, perturbação aguda e observações ainda não interpretáveis. Associe estado das evidências a cada observação relevante. Resultado visível/mudança de estado: registro publicado.
3. Publique uma classificação provisória: claro, complicado, complexo, caótico ou confuso, com as duas ou três observações que a sustentam. Se partes diferentes sustentarem classificações diferentes, divida a situação e publique limites separados, sem tirar uma média. Resultado visível/mudança de estado: classificação publicada.
4. Publique o modo correspondente: perceber–categorizar–responder para padrão repetível, perceber–analisar–responder para padrão especializado, sondar–perceber–responder para padrão adaptativo ou agir–perceber–responder para perturbação urgente. Para contexto confuso, publique a menor tarefa de enquadramento ou observação que retire a confusão. Resultado visível/mudança de estado: modo de ação publicado.
5. Publique uma próxima ação segura e sinais de aprendizagem ou transição. Declare o que será observado, por quem e quando; o sinal deve ser observável, não esperança genérica de melhora. Resultado visível/mudança de estado: registro de sinais publicado.
6. Publique estado da conclusão, evidências, uma incerteza relevante e condição que inverteria classificação ou modo de ação. Não afirme certeza apenas porque um rótulo foi escolhido. Resultado visível/mudança de estado: conclusão publicada.
7. Se limites, observação ou restrição ausente puder mudar o modo de ação, publique resultado suspenso ou provisório e pergunta ou verificação bloqueante, sem inventar fatos. Resultado visível/mudança de estado: suspensão publicada.

## Public output contract

Retorne um resultado compacto para cartão contendo `decision_question`, `domain`, `classification_evidence`, `action_mode`, `transition_signals`, `next_action` e `flip_condition`. O domínio é conclusão apoiada por observações visíveis, não distintivo. Os fundamentos usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted** quando aplicável. Inclua no máximo três pressupostos relevantes e duas incertezas não resolvidas. Se suspenso, diga o que falta e qual verificação libera a suspensão.

## Evidence and uncertainty rules

Trate observações diretas, fontes identificadas, registros do usuário e cálculos reproduzíveis como evidência apenas do que realmente sustentam. Um rótulo normalmente é inferência do padrão; não é verificado só porque uma fonte usa a mesma palavra. Não invente probabilidades de transição, impacto ou sucesso. Separe existência de retroalimentação da inferência sobre seu significado. Marque mudança de limites, classificação concorrente ou observação desatualizada como conflitante ou não verificada; reduza o apoio se puder mudar a próxima ação.

## Stop conditions

Pare e faça uma pergunta bloqueante quando limites ou observações plausíveis exigirem ações materialmente distintas e não houver escolha pelo propósito do usuário ou restrição autorizada. Suspenda se relação decisiva, restrição imediata ou sinal de transição não puderem ser estabelecidos. Termine ao publicar um modo acionável, um sinal observável e uma condição de reversão. Não espere análise exaustiva em urgência; registre contenção e revisite a classificação após novas observações.

## Complement handoff

Encaminhe a `scenario-planning` apenas quando a classificação revelar vários futuros externos coerentes que exigem preparações distintas. Transfira limites publicados, evidências de classificação, modo de ação, sinais e incerteza não resolvida. Não repita toda a classificação nem peça ao complemento um fato ausente que primeiro deveria liberar a suspensão deste procedimento.

## Purpose

Use este procedimento para executar um ciclo delimitado Plan–Do–Check–Act de uma hipótese de melhoria operacional. Torne visíveis objetivo, medida, pequeno escopo de execução, regra de comparação e decisão de padronização, acumulando melhoria como evidência e memória organizacional. É aprendizagem controlada, não substituto de diagnóstico de causa desconhecida ou resposta a incidente ativo de segurança.

## Use when

Use quando processo ou serviço admitir mudança pequena e reversível, melhoria mensurável e ciclos repetidos capazes de elevar um padrão. Serve a hipótese com janela curta de observação e decisão clara de padronizar, revisar ou abandonar. Permite aprender com execução sem comprometer toda a operação com alteração não testada.

## Do not use when

Não use se a causa fundamental for desconhecida e experimentar puder esconder ou piorar dano, se regra vinculante impedir escolhas ou se for necessária resposta urgente de segurança, proteção, legalidade ou incidente. Não execute só para criar atividade sem regra de verificação. Não transforme tarefa mecânica em programa de melhoria nem padronize porque a mudança foi anunciada ou concluída uma vez.

## Inputs to establish

Estabeleça objetivo, referência observada ou estado do processo, hipótese, escopo, responsável e direção esperada. Antes de Do, defina métrica, unidade, fonte, janela, salvaguardas, parada e comparação. Especifique evidência para padronizar, revisar ou abandonar e onde registrar próximo ciclo ou padrão versionado. Faça no máximo duas perguntas concisas, apenas se a resposta puder mudar segurança, medida ou decisão Act; marque demais lacunas como não verificadas e suspenda quando decisivas.

## Procedure

1. **Publique a ficha Plan.** Declare objetivo, referência, hipótese, direção, escopo, responsável e limite temporal. Rotule referência como verificada, calculada, fornecida pelo usuário, inferida, assumida ou não verificada. **Resultado visível/mudança de estado:** plano.
2. **Publique a especificação Check.** Nomeie métrica, unidade, fonte, coleta, janela, comparação, salvaguardas e parada. Declare previamente evidência para padronizar, revisar ou abandonar. **Resultado visível/mudança de estado:** regra de verificação.
3. **Publique o registro Do.** Execute somente no pequeno escopo aprovado; registre mudança real, desvios, exclusões, incidentes e observações. Preserve reversão e não amplie exposição por sinal inicial favorável. **Resultado visível/mudança de estado:** execução auditável.
4. **Publique o resultado Check.** Compare valores ou descrições esperados e observados pela regra prévia. Identifique dados ausentes, confundidores, limites das fontes e contradições. **Resultado visível/mudança de estado:** diferença com estado das evidências.
5. **Publique a decisão Act.** Escolha padronizar, revisar, abandonar ou suspender conforme evidências e salvaguardas. Com resultado misto ou medida decisiva ausente, mantenha mudança provisória e registre condição pendente. **Resultado visível/mudança de estado:** Act ou suspensão.
6. **Publique o próximo ciclo.** Registre padrão versionado ou hipótese revisada, responsável, próxima observação e uma ou duas condições observáveis de mudança. Transporte aprendizagem e o que continua não verificado. **Resultado visível/mudança de estado:** próximo plano ou resultado suspenso.

## Public output contract

Retorne `plan_objective_measure`, `do_scope`, `check_rule` e `act_standardize_decision`, com estado da evidência de cada fundamento material. Inclua referência inicial ou ausência em `plan_objective_measure`, exposição delimitada em `do_scope`, comparação e parada em `check_rule`; `act_standardize_decision` distingue padronizar, revisar, abandonar e suspender. Inclua hipótese do próximo ciclo ou motivo claro para não continuar. Medida decisiva ausente produz resultado suspenso.

## Evidence and uncertainty rules

Distinga observação direta, fonte vinculada, cálculo reproduzível, registro fornecido pelo usuário, inferência e premissa de trabalho. Para `computed`, mostre entradas, expressão, unidades e arredondamento pertinente. Sem referência defensável ou com coleta alterada, marque comparação como não verificada. Não invente probabilidades, efeitos, amostras ou certeza causal. Um ciclo pode sustentar aprendizagem local, raramente um padrão permanente; observações confiáveis conflitantes mantêm Act conflitante ou suspenso. Preserve desvios e sinais negativos.

## Stop conditions

Suspenda se faltarem objetivo, referência, medida, comparação, responsável ou escopo seguro que possam mudar Act. Pare imediatamente com dano contínuo, controle obrigatório enfraquecido, autorização excedida ou reversão segura perdida. Encaminhe para `root-cause-analysis` se causa desconhecida puder ser mascarada. Após verificação falha ou inconclusiva, pare sem hipótese revisada ou próxima observação segura; não repita Do sem aprender.

## Complement handoff

Encaminhe para `root-cause-analysis` se Check revelar falha recorrente, caminhos causais concorrentes ou fraqueza de controle que exija diagnóstico antes de outro ciclo. Passe plano publicado, Do delimitado, resultado, desvios, estados das evidências e questão de controle restante. Não passe acusação infundada nem inicie segundo método completo só porque o primeiro foi inconclusivo.

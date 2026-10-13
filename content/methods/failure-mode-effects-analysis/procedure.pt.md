## Purpose

Use este procedimento para identificar como processo, produto ou controle planejado pode falhar antes de depender dele. Ele liga modo de falha a efeito, causa plausível, detecção existente e controle preventivo ou de detecção. O resultado é prioridade ordinal e lista de ações com responsáveis, não escore falso de risco. Torna incerteza visível e concentra esforço em consequências ou controles frágeis que exigem atenção primeiro.

## Use when

Use-o para lançamento, mudança de fluxo, projeto de serviço, transferência, barreira de segurança, fluxo de dados ou funcionalidade com sequência e área de falhas definidas. É útil antes de compromisso, após mudança significativa de projeto ou quando incidente recorrente revela classe de falhas não examinadas. Use incidentes, testes, registros e conhecimento especializado disponíveis. Delimite ao processo ou componente descritível e acionável.

## Do not use when

Não substitua resposta emergencial, revisão jurídica, análise de perigos especializada obrigatória ou diagnóstico causal de incidente já recorrente. Não atribua números de gravidade, ocorrência ou detectabilidade sem escala, calibração e fonte. Não trate lista longa como rigor nem priorize falha só porque é fácil imaginá-la. Se limites do processo ou função pretendida forem desconhecidos, estabeleça primeiro ou suspenda.

## Inputs to establish

Nomeie processo, produto ou componente, limites, função pretendida, usuários, condições operacionais e controles atuais. Mapeie etapas ou interfaces principais e identifique perigos, restrições, incidentes, resultados de testes e responsáveis. Defina antes de classificar a linguagem ordinal, como urgente, relevante, monitorar ou baixa atenção, explicando significado local. Faça no máximo duas perguntas que poderiam mudar a ordem, como “Qual falha causaria dano irreversível?” ou “Qual controle detectaria isto antes do lançamento?”.

## Procedure

1. **Defina os limites.** Descreva função, contexto, interfaces e exclusões; divida processo grande em sequência praticável. **Resultado visível/mudança de estado:** publique limites e etapas, marcando funções ou condições desconhecidas como não verificadas.
2. **Nomeie falhas e efeitos.** Para cada etapa, declare o que pode falhar e efeito imediato, posterior, para usuário ou segurança. Mantenha modos distintos o suficiente para controles diferentes. **Resultado visível/mudança de estado:** publique registro falha-efeito ligado às etapas.
3. **Rastreie causas e controles.** Registre causas plausíveis, prevenção, detecção e evidência de funcionamento real. Separe falhas observadas de possibilidades hipotéticas. **Resultado visível/mudança de estado:** acrescente causas e controles com estados verificado, inferido, pressuposto ou não verificado.
4. **Defina prioridade ordinal.** Aplique regra qualitativa predeclarada usando consequência, exposição plausível e fraqueza de controles. Sem entradas quantitativas defensáveis, não calcule produto ou número de prioridade de risco; explique em palavras. **Resultado visível/mudança de estado:** publique lista curta ordenada e razões de urgente, relevante, monitorar ou baixa atenção.
5. **Atribua ações de controle.** Prefira prevenção que remove causa, depois detecção anterior ao dano, depois contenção que limita impacto. Nomeie responsável, gatilho, evidência de conclusão e incerteza residual. **Resultado visível/mudança de estado:** publique plano de controles ligado a cada modo priorizado.
6. **Reavalie após mudança.** Declare observação ou teste que mostraria redução da exposição ou melhor detecção e o que reabriria o modo. **Resultado visível/mudança de estado:** publique prioridade sustentada, provisória ou suspensa e condição de reversão; não encerre modo só porque uma ação foi planejada.

## Public output contract

Retorne limites, modos de falha, efeitos, causas, controles atuais, prioridade ordinal, responsável e sinal de verificação. Mostre cada item relevante como observado, inferido, pressuposto, não verificado ou conflitante. Nunca apresente escores inventados de gravidade/ocorrência/detectabilidade nem ordem precisa sem proveniência. O Cartão de Conclusão pode resumir a falha de maior atenção e condição que mudaria prioridade; o registro de rastreabilidade pode conter inventário completo.

## Evidence and uncertainty rules

Falha hipotética não é taxa observada. Controle existente não é eficaz só por estar documentado; evidências devem mostrar operação, cobertura ou teste delimitado. Separe consequência, probabilidade e detectabilidade. Use linguagem ordinal só com definição local e base declarada. Se limiar de segurança ou regulamentar for vinculante, siga exigência autorizada e marque interpretação não verificada. Se avaliações confiáveis divergirem, rotule prioridade conflitante e suspenda ordem das ações onde o conflito for relevante.

## Stop conditions

Pare quando função, limites ou condição operacional não puderem ser estabelecidos, modo de alta consequência não tiver contenção segura ou classificação depender de números inventados. Para perigo imediato, siga primeiro processo de incidente ou segurança aplicável. Suspenda recomendação de lançamento se controle decisivo não tiver sido testado ou atribuído a responsável.

## Complement handoff

Encaminhe a premortem-analysis quando um plano escolhido precisar de narrativa humana de falha e sinais precoces antes do compromisso. Transfira plano delimitado, modos priorizados, efeitos e controles; o complemento acrescenta cenários plausíveis sem transformar prioridade ordinal em falsa precisão.

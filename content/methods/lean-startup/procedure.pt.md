## Purpose

Use este procedimento para reduzir a incerteza de uma hipótese de mercado, produto ou modelo de negócio por meio de um experimento mínimo de aprendizagem. Transforme a suposição mais arriscada em teste seguro, com métrica acionável e decisão declarada previamente. Aqui, um MVP é instrumento de aprendizagem, não produto inacabado, plano completo de lançamento ou prova de demanda porque algo foi entregue.

## Use when

Use quando uma hipótese importante de valor, crescimento, adoção ou receita não foi verificada e uma pequena observação pode mudar a decisão de pivotar, perseverar ou parar. Serve a decisões de produto ou negócio com alvo identificável, exposição limitada e métrica observável. Use antes de uma expansão cara quando um teste reversível puder responder à pergunta.

## Do not use when

Não realize teste mínimo real quando segurança, lei, privacidade, proteção ou exposição irreversível de clientes ou operações o tornam inadequado. Lançamento sem medição não é experimento; métrica de vaidade não prova aprendizagem. Não use para tarefa mecânica, decisão vinculante sem liberdade experimental ou causa operacional desconhecida que deve primeiro ser diagnosticada.

## Inputs to establish

Estabeleça decisão, usuário ou contexto alvo, uma hipótese falsificável, a suposição mais arriscada e as evidências disponíveis. Defina teste mínimo ou MVP, limite de exposição, métrica acionável e unidade, janela de observação, limiar ou regra qualitativa, responsável e limite de reversão ou parada. Registre efeitos de seleção, limites de acesso e fonte da referência inicial. Faça no máximo duas perguntas concisas, somente se a resposta puder mudar segurança, métrica ou próxima decisão; caso contrário, marque a lacuna como não verificada e suspenda se decisiva.

## Procedure

1. **Publique a hipótese.** Escreva uma condição ligando ação ou oferta a contexto alvo e resultado observável. Rotule cada fundamento como verificado, calculado, inferido, assumido ou não verificado. **Resultado visível/mudança de estado:** hipótese falsificável.
2. **Publique a suposição mais arriscada.** Escolha a suposição cuja falha mais mudaria a decisão e cuja evidência é mais fraca ou conflitante. Explique importância e evidência que a enfraqueceria; preserve incerteza sem inventar probabilidade. **Resultado visível/mudança de estado:** suposição mais arriscada.
3. **Publique a ficha do teste mínimo.** Desenhe o menor teste reversível, com público ou escopo limitado, artefato, duração, responsável, limite de consentimento ou acesso e condição de parada ou reversão. Suspenda testes reais com exposição material e indique verificação mais segura sem execução real. **Resultado visível/mudança de estado:** ficha ou suspensão.
4. **Publique a especificação de medição.** Nomeie métrica, unidade, fonte, janela, referência inicial disponível e limiar ou regra decisória. Explique a ligação com a aprendizagem e rotule limiares de trabalho como suposições. **Resultado visível/mudança de estado:** medição verificável.
5. **Publique o registro do resultado.** Após teste autorizado, registre esperado versus observado, observações ausentes, seleção, desvios e estado das evidências. Não substitua resultado ausente por narrativa de sucesso; sem resultado, a hipótese continua não verificada. **Resultado visível/mudança de estado:** registro.
6. **Publique a próxima decisão.** Aplique a regra prévia: pivotar, perseverar, parar ou suspender. Declare hipótese alterada ou próximo teste, responsável, limite e uma ou duas condições observáveis de mudança. **Resultado visível/mudança de estado:** decisão delimitada.

## Public output contract

Retorne campos prontos para ficha: `hypothesis`, `riskiest_assumption`, `minimum_test`, `metric_threshold` e `next_decision`. O teste declara escopo seguro, sinal observável e condição de parada ou reversão. A métrica identifica fonte e unidade; a decisão distingue pivotar, perseverar, parar e suspender. Inclua no máximo duas incertezas materiais no resultado resumido. Métrica decisiva, limiar ou resultado ausente produz estado não verificado ou suspenso, não recomendação irrestrita.

## Evidence and uncertainty rules

Entrega não prova demanda; métrica não prova automaticamente causalidade. Observações diretas e fontes vinculadas são verificadas apenas se sustentarem o fundamento específico; mostre entradas e expressões de cálculos, marque raciocínio de modelo como inferência, limiar escolhido ou premissa não testada como suposição, verificação ausente como não verificada e discordância como conflito. Declare contexto testado, limites de acesso ou seleção e janela. Não invente probabilidades, conversões, amostras ou reações de clientes. Um teste atualiza aquela hipótese naquele contexto, sem generalizar para todos os usuários ou períodos futuros.

## Stop conditions

Suspenda se faltarem decisão, contexto, suposição mais arriscada, métrica acionável ou regra e isso puder mudar o resultado. Pare teste inseguro, ilegal, invasivo, sensível à segurança, irreversível ou não autorizado. Pare sem sinal capaz de distinguir alternativas, sem reversão obrigatória ou se o resultado deriva de métrica de vaidade. Encaminhe falha operacional de causa desconhecida; não a disfarce com experimento de produto.

## Complement handoff

Encaminhe para `jobs-to-be-done` quando a descoberta do trabalho, contexto ou progresso desejado do usuário precisar preceder a hipótese. Passe apenas contexto alvo, hipótese, suposição mais arriscada, estado observado das evidências e necessidade não resolvida. Não repita o experimento nem sugira que encaminhamento fornece resultados ausentes. Use primeiro `assumption-mapping` se várias suposições precisarem de priorização.

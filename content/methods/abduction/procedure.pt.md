## Purpose

Use este procedimento para comparar explicações concorrentes de um fato observado ou surpreendente e selecionar a melhor explicação atual sem apresentá-la como comprovada. Ele exige pelo menos duas candidatas ainda plausíveis, avalia adequação explicativa e risco e identifica evidências capazes de distingui-las. O resultado é um diagnóstico provisório com uma próxima verificação concreta, não uma autorização para adaptar os fatos à narrativa preferida.

## Use when

Use-o na depuração, no diagnóstico, na investigação, na interpretação de anomalias e em outras situações em que várias causas possam explicar a mesma observação. É adequado para informações incompletas e perguntas sobre o que provavelmente está acontecendo ou por que ocorreu um resultado inesperado. Use-o quando uma regra dedutiva ainda não determina o resultado.

## Do not use when

Não o use quando regras explícitas e premissas estabelecidas implicam a conclusão, ou quando nenhuma observação pode distinguir as explicações. Não trate uma única candidata como um conjunto de explicações, não atribua precisão inventada a uma narrativa nem considere a ausência de uma observação contrária como confirmação. Evite certeza causal quando as candidatas são apenas interpretações descritivas.

## Inputs to establish

Estabeleça a observação surpreendente, a referência esperada, a decisão ou o diagnóstico afetado, os fatos conhecidos, as explicações candidatas plausíveis e os testes ou as fontes disponíveis. Identifique se cada candidata é uma causa, um mecanismo, um erro de dados ou uma explicação de escopo. Faça no máximo uma pergunta decisiva se a observação ou o alvo da decisão não estiver claro; caso contrário, prossiga com pressupostos explícitos.

## Procedure

1. Publique a observação que exige explicação e a referência que ela contraria. Marque quais partes são fatos verificados, relatos do usuário ou pressupostos; isso cria o estado visível da anomalia.
2. Publique pelo menos duas explicações candidatas com suas observações previstas e seu escopo. Acrescente uma candidata de erro de medição, seleção ou relato quando plausível, sem tratar a primeira narrativa substantiva como padrão.
3. Publique uma comparação qualitativa de adequação explicativa, abrangência, simplicidade, consistência com o conhecimento estabelecido e possibilidade de teste. Use classificações ordinais como forte, moderada, fraca ou desconhecida; não invente probabilidades.
4. Publique evidências discriminantes: a observação, o experimento ou a fonte que separaria as principais candidatas. Declare qual resultado aumentaria, diminuiria ou manteria o suporte a cada candidata.
5. Publique a melhor explicação atual e por que ela está à frente, com estado provisório. Mantenha as alternativas visíveis e declare se o resultado é um diagnóstico, uma hipótese de trabalho ou um conjunto não resolvido.
6. Publique a próxima ação de verificação e o modo de falha relevante, incluindo o que mostraria que a explicação está errada ou que o vínculo com a evidência não é confiável.
7. Publique a conclusão atual, o conjunto de candidatas e uma condição observável de reversão. Se nenhuma candidata tiver suporte discriminante ou faltar uma observação decisiva, suspenda o resultado em vez de escolher a narrativa mais vívida.

## Public output contract

Retorne `observation`, `candidate_explanations`, `comparison_criteria`, `discriminating_evidence`, `provisional_best_explanation`, `next_test` e `flip_condition`. A primeira linha deve dizer “melhor explicação atual” ou equivalente quando o resultado for provisório. Os fundamentos recebem os rótulos **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**; a adequação de uma candidata é uma inferência, não uma prova direta.

## Evidence and uncertainty rules

Um fato surpreendente pode motivar uma hipótese, mas não estabelecer sua causa. Exija suporte independente ou discriminante antes de elevar uma candidata. Evite contar duas vezes a mesma observação em vários critérios. Se as candidatas se ajustarem igualmente bem, relate uma competição não resolvida. Se um teste relevante estiver indisponível, mantenha a melhor explicação provisória ou suspensa e declare a evidência ausente.

## Stop conditions

Pare e faça uma pergunta bloqueante quando a observação ou o alvo da decisão for vago demais para identificar explicações candidatas. Suspenda quando só houver uma candidata, não existir implicação testável ou faltar evidência decisiva. Pare quando premissas explícitas implicarem o resultado ou quando a tarefa restante for qualidade de fontes, validade formal ou comparação de opções.

## Complement handoff

Encaminhe a `value-of-information` quando a decisão principal for comprar, coletar ou aguardar informações discriminantes. Transfira o conjunto de candidatas, as evidências que mudariam a decisão e o custo ou atraso do próximo teste. O complemento não deve repetir a comparação das explicações.

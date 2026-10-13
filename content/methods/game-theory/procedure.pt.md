## Purpose

Use este procedimento quando o resultado de uma decisão depende da resposta de outro ator, cujo resultado também depende dessa decisão. Ele torna visíveis jogadores, ações disponíveis, incentivos, informação, temporalidade e compromissos críveis antes de recomendar um movimento. Não autoriza inventar tabela de ganhos, atribuir probabilidades nem chamar resultado de equilíbrio sem suporte das evidências.

## Use when

Use-o para movimentos competitivos, negociação, licitação, preços, entrada ou dissuasão, contratos, padrões compartilhados e escolhas em que outra parte pode adaptar-se estrategicamente. Ajuda quando falta saber “o que farão se fizermos isto?” ou promessa, ameaça, reputação ou vantagem informacional pode alterar resultado. Declare interação repetida e possibilidade de cooperação, sem pressupô-las.

## Do not use when

Não o use para otimização de um ator sem resposta estratégica significativa do ambiente, regra vinculante sem escolha, escolha mecânica ou situação em que o suposto oponente não afeta resultado. Não reduza relação negociada à competição de soma zero sem evidência. Não infira racionalidade, motivos ocultos ou ganho numérico apenas porque uma ação parece conveniente.

## Inputs to establish

Estabeleça decisão focal, jogadores e direitos decisórios, ações viáveis, resultado valorizado por cada jogador, informação disponível, ordem dos movimentos e interação única ou repetida. Registre compromissos críveis, restrições e comportamento anterior apenas com fonte ou fornecimento explícito. Ganhos podem permanecer ordinais ou qualitativos sem escala defensável. Faça no máximo duas perguntas concisas, apenas se jogador, ação, incentivo, informação ou temporalidade ausentes mudarem a recomendação.

## Procedure

1. Publique decisão focal e registro de jogadores, incluindo quem age, é afetado, veta ou atrasa. Marque funções observadas, fornecidas pelo usuário, inferidas ou pressupostas. Resultado visível/mudança de estado: limites do jogo publicados.
2. Publique ações e informação de cada jogador: ações viáveis, observável por cada um, movimentos simultâneos ou sequenciais e repetição da interação. Isso especifica uma disputa vaga. Resultado visível/mudança de estado: estrutura publicada.
3. Publique registro de incentivos dos resultados relevantes com consequências de fontes ou do usuário, rotuladas verified, computed, inferred, assumed, unverified ou conflicted. Preserve comparação ordinal quando ganhos exatos não forem defensáveis. Resultado visível/mudança de estado: incentivos publicados.
4. Publique verificação de respostas: compare melhores respostas críveis em contexto simultâneo ou raciocine retroativamente da decisão final em contexto sequencial. Se houver ação dominante sustentada, explique; caso contrário, mostre pares relevantes sem fingir conhecer todos os motivos. Resultado visível/mudança de estado: respostas publicadas.
5. Publique resultados estáveis candidatos e se há um, vários ou nenhum sustentado. Use equilíbrio só com pressupostos de ações, incentivos, informação e temporalidade suficientemente evidenciados; caso contrário, chame condicional e declare o ausente. Resultado visível/mudança de estado: resultado publicado.
6. Publique alavancas de intervenção e movimento recomendado. Explique se mudam incentivos, informação, temporalidade, ações ou credibilidade de compromissos e associe um sinal observável de resposta. Resultado visível/mudança de estado: movimento e sinal publicados.
7. Publique conclusão, incerteza mais forte e condição observável que inverteria o movimento. Sem fato decisivo de ganho, jogador ou temporalidade, suspenda e declare menor verificação para liberar, sem escolher vencedor fictício. Resultado visível/mudança de estado: suspensão publicada.

## Public output contract

Retorne `players`, `actions`, `incentives`, `information`, `timing`, `response_analysis`, `candidate_outcome`, `equilibrium_caveat`, `move` e `flip_condition`. Resultado candidato não é automaticamente desejável, justo, eficiente ou inevitável. Declare sustentado, condicional, conflitante ou suspenso. Fundamentos usam rótulos de evidência do cartão; alternativas resumem movimentos ou compromissos materialmente distintos. Não exponha transcrição privada de raciocínio.

## Evidence and uncertainty rules

Separe comportamento observado de teoria de motivos. Alegação de ganho exige fonte, registro do usuário, cálculo reproduzível ou pressuposto explícito; rotule fonte e escopo. Não invente probabilidades, taxas de desconto, informação oculta ou racionalidade. Padrão estável significa que nenhuma mudança unilateral sustentada melhora o resultado declarado sob os pressupostos declarados; não prova desejabilidade social. Ameaça ou promessa conta apenas se o ator ainda teria razão para cumpri-la na decisão relevante. Marque incentivos ausentes, conflitantes ou antigos como não verificados ou conflitantes e reduza o apoio.

## Stop conditions

Pare e faça pergunta bloqueante se conjuntos plausíveis de jogadores, ações ou temporalidades levarem a movimentos distintos e o propósito não escolher. Suspenda sem incentivo, informação ou sequência decisiva. Pare sem selecionar método se não houver interdependência estratégica significativa. Termine com estrutura, resposta condicional, movimento, evidência e sinal públicos; não continue calculando para criar falsa precisão.

## Complement handoff

Encaminhe a `stakeholder-analysis` apenas se estrutura revelar questões relevantes de poder, consentimento, legitimidade, apoio de implementação ou grupos afetados não representados. Transfira jogadores, incentivos, conflitos, compromissos e incerteza. O complemento mapeia atores e engajamento; não repete respostas nem fabrica ganhos ausentes.

## Purpose

Use este procedimento para calibrar uma alegação à qualidade, relação direta, aplicabilidade e risco de viés das fontes de apoio. Ele classifica o tipo de alegação, compara desenhos de estudos ou evidências sem tratar hierarquia rígida como universal e declara estado das evidências e força da conclusão. Uma fonte de nível inferior ainda pode ajudar quando corresponde diretamente à pergunta e desenhos superiores não.

## Use when

Use-o quando pesquisa, política, experimentos de produto, opinião especializada, relatos de usuários ou outras evidências estão misturados e a resposta exige rótulo de força defensável. Serve para saber se fontes sustentam alegação, se estudo se aplica ao contexto-alvo e como a redação deve mudar com a qualidade das evidências.

## Do not use when

Não o use quando a disputa principal é preferência de valor, não suporte factual, ou quando método de regra formal, modelo causal ou conflito de fontes é mais específico. Não classifique evidências só pelo prestígio, descarte automaticamente fontes inferiores relevantes nem chame fonte de forte sem verificar relação direta e limitações.

## Inputs to establish

Estabeleça alegação, população ou contexto-alvo, tipo de alegação (efeito, previsão, mecanismo ou experiência), limiar decisório, fontes, desenhos, amostras, medidas e conflitos conhecidos. Identifique fonte direta, indireta ou apenas contextual. Faça no máximo uma pergunta decisiva quando contexto-alvo modificar aplicabilidade.

## Procedure

1. Publique alegação, contexto-alvo e limiar decisório. Declare se trata de efeito, previsão, mecanismo ou experiência; isso cria estado visível da revisão.
2. Publique tabela alegação-fonte com tipo, desenho, amostra ou base, relação direta e escopo. Marque cada fonte verificada, fornecida pelo usuário, inferida ou indisponível.
3. Publique dimensões de qualidade: rigor do desenho, viés, validade da medição, completude e aplicabilidade, com rótulos qualitativos ou ordinais de proveniência declarada. Não invente escore composto preciso.
4. Publique posição hierárquica e limites de cada fonte. Explique por que é forte ou fraca para esta alegação específica, sem transformar posição em autoridade universal.
5. Publique concordância, inconsistência e evidências ausentes entre fontes. Mantenha conflito confiável visível; não calcule média de resultados incompatíveis sem regra de síntese justificada.
6. Publique estado resultante e conclusão calibrada: fortemente sustentada, sustentada, provisória, não verificada, conflitante ou suspensa. Declare a menor limitação de fonte ou aplicabilidade que restringe a linguagem.
7. Publique próxima ação de verificação e condição observável de reversão. Se faltar suporte decisivo, suspenda ou reduza a alegação, sem apresentar conclusão de alto impacto como estabelecida.

## Public output contract

Retorne `claim`, `claim_type`, `claim_to_source_table`, `quality_limits`, `quality_dimensions`, `hierarchy_position_and_limits`, `agreement_and_conflicts`, `missing_evidence`, `resulting_evidence_state`, `calibrated_conclusion` e `flip_condition`. O cartão mostra estado das evidências e vínculo seguro à fonte ou rótulo de informação do usuário quando aplicável. Fundamentos usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**.

## Evidence and uncertainty rules

Hierarquia de desenhos é orientação, não substituto de adequação à pergunta. Verifique relação direta, população, resultado, tempo, medição, seleção, perdas de participantes e viés de relato. Opinião especializada pode identificar mecanismo sem estimar efeito; relato de usuário pode revelar experiência sem estabelecer prevalência. Se fontes divergirem materialmente ou a melhor for indireta, reduza o apoio ou suspenda e nomeie a limitação.

## Stop conditions

Pare e faça pergunta bloqueante se contexto-alvo ou alegação forem indefinidos e aplicabilidade mudar a decisão. Suspenda se nenhuma fonte sustentar diretamente alegação relevante, conflito não for resolvido ou limites de qualidade impedirem rótulo seguro de força. Pare se a questão for escolha de valores, implicação formal ou gerar explicações, não calibrar evidências.

## Complement handoff

Encaminhe a `triangulation` quando fluxos independentes de evidência puderem corroborar ou revelar conflito relevante. Transfira tabela alegação-fonte, limites de qualidade e divergência não resolvida. O complemento verifica independência e convergência sem reconstruir a classificação das fontes.

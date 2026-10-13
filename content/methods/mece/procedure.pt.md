## Purpose

Use este procedimento para testar se uma classificação ou decomposição é mutuamente exclusiva e coletivamente exaustiva no mesmo nível. Fixe um eixo, teste sobreposição e lacunas separadamente e mantenha granularidade consistente. O resultado é uma regra defensável com casos de fronteira conhecidos, não promessa de que todas as categorias reais sejam naturalmente bem separadas.

## Use when

Use quando categorias, grupos de responsabilidade, opções, requisitos, causas ou ramos duplicarem ou omitirem casos materiais. É útil na revisão de classificação existente e como verificação focada dentro de árvore lógica ou estrutura executiva. Use quando o gargalo decisório for a regra de classificação, não uma fonte factual.

## Do not use when

Não use quando a sobreposição natural for o fenômeno estudado, as categorias representarem intencionalmente eixos diferentes ou uma taxonomia vinculante só precisar ser aplicada. Não misture idade, geografia, intenção e etapa do processo no mesmo nível. Não esconda classe grande em outros nem force exclusividade quando houver pertencimento legítimo a vários rótulos.

## Inputs to establish

Estabeleça universo, finalidade decisória, categorias candidatas, eixo único proposto, regras de inclusão e exclusão e casos de fronteira conhecidos. Declare se há rótulo único ou múltiplos. Faça no máximo uma pergunta se universo ou finalidade forem materialmente ambíguos; caso contrário, declare um universo delimitado.

## Procedure

1. Publique em uma frase universo, finalidade e um eixo. Isso fixa o estado visível e evita critérios misturados.
2. Publique categorias candidatas com uma regra de inclusão e uma de exclusão para cada. Marque fronteiras como explícitas, inferidas ou não verificadas.
3. Publique o teste de exclusão mútua com casos plausíveis que caberiam em duas categorias. Para cada sobreposição, una, redefina divisões ou permita explicitamente múltiplos rótulos; registre a mudança.
4. Publique o teste de cobertura coletiva com casos extremos e observações conhecidas. Acrescente categoria somente se o caso ausente pertencer ao universo declarado; caso contrário, restrinja o universo e divulgue a exclusão.
5. Publique verificação de granularidade do nível: compare abstração, tamanho e uso decisório. Refaça categoria que seja subcategoria oculta das demais ou ampla demais para ação.
6. Publique casos de fronteira, regra final e sobreposição intencionalmente não resolvida. Não use um grupo vago de outros para parcela material do universo.
7. Publique classificação, veredicto de sobreposição/lacuna e condição observável de mudança. Se o eixo não sustentar a decisão ou caso importante não admitir classificação, suspenda em vez de forçar rótulo.

## Public output contract

Retorne `classification_universe`, `classification_rule`, `classification_axis`, `categories`, `inclusion_rules`, `exclusion_rules`, `overlap_gap_check`, `overlap_check`, `coverage_check`, `granularity_check`, `boundary_cases` e `flip_condition`. Distinga ME de CE e declare rótulo único ou múltiplo. Os fundamentos usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**; categorias não são evidência de prevalência.

## Evidence and uncertainty rules

ME e CE são testes lógicos de cobertura, não prova empírica de utilidade. Um exemplo pode revelar sobreposição ou lacuna sem estabelecer frequência. Separe observações apoiadas em fontes de escolhas de desenho das categorias. Se faltar categoria material, permanecer caso contestado ou o eixo mudar a decisão, rotule o resultado como provisório ou suspenso.

## Stop conditions

Pare e faça uma pergunta bloqueadora se universo ou finalidade não puderem ser delimitados. Suspenda se o eixo não representar casos materiais sem sobreposição enganosa, ou se uma categoria ausente mudar a decisão. Pare quando a regra passar em ME/CE no escopo exigido e o restante for decomposição estrutural ou comparação de opções.

## Complement handoff

Encaminhe para `logic-tree` quando categorias validadas formarem o primeiro nível de diagnóstico ou plano mais amplo e precisarem de ramos recursivos e testes das folhas. Passe universo, eixo, categorias finais, casos de fronteira e veredicto de cobertura. O complemento não repete MECE no mesmo nível.

## Purpose

Use este procedimento para transformar um termo ambíguo ou contestado em uma definição útil à decisão, sem fingir que uma entrada de dicionário resolve a questão. Ele separa significados concorrentes, testa condições candidatas com exemplos e casos limítrofes e registra o que decorre do significado operacional escolhido. O resultado sustenta ação, medição ou política, mantendo visível a ambiguidade residual.

## Use when

Use-o quando termos como seguro, justo, qualidade, pronto, confiável, sustentável ou bem-sucedido determinam a decisão e pessoas diferentes podem usá-los de maneiras distintas. É adequado a políticas, requisitos de produto, critérios de avaliação, contratos, perguntas de pesquisa e divergências parcialmente relacionadas ao significado. Também é útil antes do mapeamento de argumentos quando uma palavra compartilhada oculta alegações diferentes.

## Do not use when

Não o use quando o termo relevante já tiver definição operacional estável em especificação autorizada e bastar aplicá-la ou verificá-la. Não resolva disputas factuais reescrevendo uma definição, nem trate um julgamento moral preferido como essência descoberta. Uma definição não substitui evidências de que um caso a satisfaz.

## Inputs to establish

Estabeleça o termo-alvo, a decisão ou medição que ele controla, o falante ou documento que o utiliza e o contexto relevante. Reúna poucos casos claramente positivos e negativos e até três casos limítrofes. Registre qualquer definição autorizada, preferência do usuário e consequência prática. Faça no máximo duas perguntas, apenas se o contexto pretendido ou uso decisório não puder ser delimitado de outra forma.

## Procedure

1. Publique em uma frase o conceito-alvo, o contexto e a decisão controlada. Marque se o contexto veio do usuário, de documento aplicável ou de pressuposto; isso cria o estado visível da análise.
2. Publique dois a quatro significados concorrentes, cada um com fonte ou falante e resultado permitido. Não reduza usos diferentes a um só apenas porque compartilham uma palavra.
3. Publique casos claramente positivos e negativos e mapeie quais significados candidatos classificam cada caso. Isso mostra se a divergência é semântica, factual ou ambas.
4. Publique separadamente condições necessárias e suficientes candidatas. Para cada uma, declare se é sustentada, proposta ou não verificada; nunca trate uma condição plausível como estabelecida.
5. Publique testes limítrofes e contraexemplos. Mostre o caso que mais ameaça o significado escolhido e se a regra deve ser restringida, ampliada ou permanecer sem solução.
6. Publique um significado operacional, seu escopo, exclusões e ambiguidade residual. Declare a consequência para a decisão, medição ou requisito atual e explicite a mudança de estado resultante.
7. Publique o vínculo conceito-decisão e uma condição observável de reversão. Se nenhuma definição classificar confiavelmente o caso decisivo, suspenda o julgamento, sem escolher um rótulo por conveniência.

## Public output contract

Retorne `concept`, `competing_meanings`, `chosen_operational_meaning`, `necessary_conditions`, `sufficient_conditions`, `boundary_cases`, `residual_ambiguity`, `consequence`, `decision_consequence` e `flip_condition`. A conclusão deve dizer o que o significado escolhido permite ou exclui, não afirmar uma essência atemporal do conceito. Mantenha no máximo três pressupostos relevantes e duas incertezas não resolvidas. Os fundamentos do cartão recebem **verified**, **inferred**, **assumed**, **unverified** ou **conflicted**; exemplos só são evidências quando sua proveniência e relevância forem declaradas.

## Evidence and uncertainty rules

Uma definição autorizada sustenta como um termo é usado, não se o mundo a satisfaz. Distinga definição apoiada por fonte, convenção escolhida pelo usuário e operacionalização proposta. Um caso limítrofe não classificável não prova que qualquer lado tem razão; evidencia ambiguidade residual. Se significados concorrentes levarem a ações diferentes de alto impacto, divulgue o conflito e reduza o apoio ou suspenda a conclusão até selecionar o contexto autorizado.

## Stop conditions

Pare e faça uma pergunta bloqueante quando leituras plausíveis tornarem o contexto-alvo realmente incompatível e não for possível delimitar com segurança a decisão do usuário. Suspenda quando o caso decisivo continuar não classificável ou faltarem evidências necessárias para aplicar o significado operacional. Pare quando o termo for estável, a disputa for factual e outro método puder tratar as evidências restantes.

## Complement handoff

Encaminhe a `argument-mapping` quando o significado escolhido revelar alegações concorrentes, premissas compartilhadas ou objeções que exijam separação estrutural. Transfira apenas significado operacional selecionado, caso limítrofe relevante e consequência não resolvida. O complemento não deve repetir todo o inventário de definições.

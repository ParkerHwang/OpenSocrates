## Purpose

Use este procedimento para mostrar como alegações, fundamentos, objeções e refutações sustentam ou enfraquecem uma conclusão. Ele cria um mapa de argumentos auditável, em vez de um mapa mental livre, mantendo visíveis as premissas compartilhadas, os vínculos sem suporte e as objeções não resolvidas. O procedimento pode esclarecer uma disputa antes de uma decisão, mas organizar uma premissa em uma estrutura clara não a torna verdadeira.

## Use when

Use-o quando um argumento de política, direito, estratégia, pesquisa ou produto contém várias alegações aninhadas e não está claro qual evidência sustenta cada conclusão. É adequado para disputas com várias objeções, refutações ou pressupostos compartilhados. Use-o quando a tarefa principal for separar relações de apoio e ataque e declarar a força resultante ou a condição de suspensão.

## Do not use when

Não o use para uma lista simples, um cálculo direto ou uma tarefa cujo único problema é a qualidade das fontes. Não desenhe associação, cronologia ou semelhança temática como se fossem apoio lógico. Não infira que uma conclusão é sólida porque seu mapa está completo, nem esconda escolhas de valor em premissas aparentemente neutras.

## Inputs to establish

Estabeleça a conclusão-alvo, a decisão ou pergunta, o escopo relevante, os fundamentos diretos, as premissas compartilhadas, as objeções, as refutações e as fontes disponíveis. Identifique se cada item é fato, regra, inferência, preferência ou pressuposto. Faça no máximo duas perguntas decisivas quando uma alegação ou um escopo ausente alteraria o mapa; caso contrário, marque a lacuna e prossiga.

## Procedure

1. Publique a conclusão principal e a decisão que ela pretende sustentar. Marque seu estado atual como sustentada, provisória, em conflito ou suspensa; isso cria o estado visível do argumento.
2. Publique as premissas de apoio direto e distinga-as das premissas necessárias em conjunto. Desenhe apenas vínculos explícitos de apoio e rotule cada vínculo como declarado, inferido ou não verificado.
3. Publique os subfundamentos de cada premissa, preservando a hierarquia entre alegações e fundamentos. Acrescente referências a fontes ou cálculos quando disponíveis e registre os vínculos sem suporte como lacunas.
4. Publique as objeções como ramos separados de ataque; publique refutações apenas quando responderem à alegação real da objeção. Marque uma objeção como não resolvida quando a refutação não modificar sua evidência nem seu escopo.
5. Publique premissas ocultas ou compartilhadas e teste se retirar cada uma modifica a conclusão. Essa mudança de estado identifica a menor fragilidade relevante, em vez de contar todas as frases igualmente.
6. Publique um veredito do mapa: vínculo mais bem sustentado, vínculo mais fraco, objeção não resolvida e qualquer ramo redundante ou irrelevante. Distinga a completude do mapa da verdade das premissas e da validade das inferências.
7. Publique o estado atual das evidências da conclusão e uma condição observável de reversão. Se faltar uma premissa relevante ou uma objeção decisiva permanecer sem solução, reduza o apoio à conclusão ou suspenda-a, sem reparar silenciosamente o argumento.

## Public output contract

Retorne `claim_ground_objection_map`, `top_level_conclusion`, `direct_grounds`, `shared_premises`, `subgrounds`, `objections`, `rebuttals`, `unsupported_links`, `map_verdict` e `flip_condition`. O resultado público deve mostrar um mapa compacto de alegações, fundamentos e objeções, não uma transcrição privada do raciocínio. Os fundamentos recebem **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**. Inclua apenas ramos relevantes no cartão e envie os detalhes ao registro de rastreabilidade quando necessário.

## Evidence and uncertainty rules

Uma fonte pode sustentar uma alegação sem sustentar o vínculo entre ela e a conclusão. Avalie separadamente a relação direta, a relevância e o escopo. Premissas compartilhadas não devem ser contadas duas vezes como suporte independente. Uma refutação que questiona uma testemunha ou medição pode enfraquecer o vínculo de apoio sem provar a conclusão oposta. Fundamentos confiáveis em conflito exigem um conflito visível e um resultado suspenso ou com apoio reduzido, salvo quando uma regra declarada de precedência resolver o conflito.

## Stop conditions

Pare e faça uma pergunta bloqueante quando a conclusão-alvo ou o escopo da decisão estiver ausente e interpretações concorrentes criarem mapas diferentes. Suspenda quando uma premissa relevante não puder ser sustentada ou uma objeção decisiva não tiver solução. Pare quando a tarefa for apenas classificar fontes, calcular algo simples ou estabelecer uma definição estável; encaminhe ao método mais específico.

## Complement handoff

Encaminhe a `evidence-hierarchy` quando o mapa mostrar que a qualidade das fontes, o desenho dos estudos ou sua relação direta com as alegações, e não a estrutura argumentativa, é o gargalo restante. Transfira apenas os vínculos entre alegações e fontes, os vínculos sem suporte e o conflito relevante. O complemento não deve reconstruir todo o mapa de argumentos.

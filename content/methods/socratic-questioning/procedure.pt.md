## Purpose

Use este procedimento quando poucas respostas do usuário puderem mudar materialmente questão, padrão de evidência ou recomendação. Revele suposições, significados, fundamentos, alternativas e implicações por perguntas, mantendo responsabilidade por resposta delimitada. Perguntas ajudam a decidir; não evitam resposta nem conduzem a conclusão predeterminada.

## Use when

Use se afirmação, termos, escopo, evidências ou consequência desejada estiverem pouco claros e breve esclarecimento mudar encaminhamento. Serve a orientação, ensino, deliberação, autorrevisão e definição colaborativa do problema. No julgamento, pergunte apenas por respostas realmente decisivas; caso contrário, declare suposição razoável e prossiga.

## Do not use when

Não use para tarefa mecânica, resposta segura com suposição delimitada ou perguntas repetidas que só atrasem ação. Não solicite raciocínio privado, dados pessoais desnecessários ou entrevista aberta. Não use perguntas indutivas que pressupõem resposta desejada.

## Inputs to establish

Estabeleça afirmação ou decisão, termos a esclarecer, escopo atual, evidências, alternativas consideradas e consequência relevante ao usuário. Selecione no máximo três perguntas decisivas. Para cada, declare efeito da resposta sobre enquadramento, evidência, ordem das opções ou conclusão da tarefa. Defina alternativa segura caso o usuário não responda.

## Procedure

1. Publique reformulação neutra da afirmação ou decisão e ponto pendente, criando questão compartilhada sem implicar concordância.
2. Publique até três perguntas delimitadas, com efeito decisório e formato curto ou faixa permitida de resposta. Esse conjunto visível é o único pedido de esclarecimento; não acrescente questionário oculto.
3. Registre cada resposta como fornecida pelo usuário, não respondida ou ambígua; publique efeito imediato sobre escopo, termos, evidências ou alternativas. Torne visível a mudança de julgamento.
4. Publique fundamento de apoio mais forte e um contraexemplo ou alternativa confiável levantado pelas respostas. Distinga resposta de evidência sobre o mundo.
5. Publique conclusão provisória ou próxima ação delimitada, incluindo o que pode ser feito sem nova pergunta. Se uma resposta mudar encaminhamento, declare-o em linguagem simples.
6. Publique incerteza restante e condição observável de mudança. Marque perguntas não respondidas como suposições só se a suposição for segura e reversível.
7. Publique resposta atual, por que decorre das entradas respondidas e se tarefa está concluída, provisória ou suspensa. Não fabrique certeza se faltar resposta decisiva.

## Public output contract

Retorne `no_more_than_three_decisive_questions`, `decisive_questions` (máximo três), `why_each_matters`, `answers_and_status`, `decision_effects`, `provisional_conclusion`, `remaining_uncertainty`, `next_action` e `flip_condition`. Perguntas são visíveis e delimitadas; a ficha final não expõe transcrição de deliberação privada. Inclua no máximo duas incertezas pendentes. Fundamentos usam **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**.

## Evidence and uncertainty rules

Respostas estabelecem preferências, escopo ou contexto, salvo evidência verificável adicional. Não promova resposta a **verified** sem fonte identificável de apoio. Pergunta decisiva não respondida mantém afirmação **assumed**, **unverified** ou **held**, conforme materialidade. Mostre respostas conflitantes e não acrescente pergunta, salvo uma curta capaz de resolver com segurança.

## Stop conditions

Pare e faça as perguntas selecionadas se seguir sem elas mudar materialmente ação. Faça no máximo três; se o usuário não puder responder, prossiga com suposição reversível ou suspenda julgamento. Pare de perguntar quando encaminhamento e conclusão estiverem estáveis para agir, ou quando restar trabalho mecânico sem julgamento.

## Complement handoff

Encaminhe para `assumption-mapping` somente se respostas revelarem várias suposições materiais a priorizar e testar. Passe perguntas respondidas e não respondidas, estados das suposições e condição de mudança atual. Não repita perguntas socráticas nem crie entrevista ilimitada.

## Purpose

Use este procedimento para transformar julgamento ou análise sólidos em resposta executiva cuja ideia central venha primeiro. Agrupe razões no mesmo nível, verifique se cada afirmação superior resume detalhes de apoio e escolha uma ordem consistente para pontos equivalentes. Melhore a comunicação sem fazer julgamento pendente parecer resolvido.

## Use when

Use para relatórios, memorandos decisórios, resumos executivos, propostas, apresentações ou pedidos de começar pela resposta. Serve a análise longa com conclusão suficientemente sustentada, mas difícil de percorrer. Use depois de verificar julgamento e evidências subjacentes.

## Do not use when

Não use para ignorar evidência ausente, ocultar conflito material ou escolher conclusão que a análise ainda não estabeleceu. Não force três grupos com sobreposição ou omissão relevante. Não coloque contexto antes de conclusão direta disponível, mas preserve escopo e incerteza necessários na ficha.

## Inputs to establish

Estabeleça pergunta principal, conclusão atual, fundamentos materiais, alternativas, decisão do público, escopo e estado das evidências. Escolha ordem dedutiva, temporal, estrutural ou de importância para razões equivalentes. Faça no máximo uma pergunta se faltar decisão do público ou conclusão; caso contrário, declare público pretendido e prossiga.

## Procedure

1. Publique pergunta principal e ideia central de uma frase no topo. Marque conclusão sustentada, provisória, conflitante ou suspensa; isso cria estado visível da comunicação.
2. Publique de três a quatro grupos de razões que sustentem conjuntamente a ideia. Dê mensagem principal de uma linha a cada grupo e registre sobreposição ou cobertura ausente como lacuna estrutural.
3. Publique detalhes de apoio sob cada grupo e verifique relação vertical: a mensagem resume os detalhes, não introduz afirmação nova.
4. Publique e aplique consistentemente ordem horizontal dedutiva, temporal, estrutural ou de importância. Registre ordem alternativa que mude materialmente interpretação.
5. Publique resposta principal, razões agrupadas e detalhes de cima para baixo. Preserve suposições, conflitos e fundamentos não verificados necessários, sem removê-los no polimento.
6. Publique alternativa ou contra-argumento mais forte e motivo da não escolha. Se julgamento subjacente estiver pendente, mude o estado para provisório ou suspenso em vez de resposta executiva definitiva.
7. Publique estrutura final pronta para ficha e condição observável de mudança. Confirme presença de entrega solicitada, restrições explícitas, verificações de evidência e divulgação de incerteza.

## Public output contract

Retorne `top_line_answer`, `governing_thought`, `grouped_reasons`, `reason_groups`, `supporting_detail_order`, `scope_and_assumptions`, `alternatives_considered`, `completion_check` e `flip_condition`. A primeira frase é conclusão; contexto só vem depois como apoio. Limite fundamentos da ficha a afirmações materiais e rotule **verified**, **computed**, **inferred**, **assumed**, **unverified** ou **conflicted**. A estrutura pode estar em memorando, preservando conclusão primeiro.

## Evidence and uncertainty rules

Boa estrutura não melhora o nível das evidências. Cada grupo de razões precisa de base visível; ligações inferidas não são fatos diretos. Mostre conflitos entre grupos sem suavizá-los em narrativa. Se fundamento, alternativa ou item de conclusão ausente mudar a resposta, use conclusão provisória ou suspensa e nomeie o item.

## Stop conditions

Pare e faça uma pergunta bloqueadora sem pergunta central estável ou decisão do público quando respostas principais possíveis diferirem materialmente. Suspenda se julgamento não for sustentado, for conflitante ou incompleto. Pare quando resposta já estiver clara e restar formatação mecânica; não acrescente comentário metodológico a esse trabalho.

## Complement handoff

Encaminhe para `argument-mapping` quando grupos revelarem apoio, objeção ou premissa compartilhada não resolvidos. Passe ideia central, grupos materiais e uma ligação pendente. O complemento não reorganiza a resposta executiva pronta nem produz segunda pirâmide completa.

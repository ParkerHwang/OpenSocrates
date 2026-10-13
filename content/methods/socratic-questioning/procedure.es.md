## Purpose

Usa este procedimiento cuando pocas respuestas del usuario puedan cambiar materialmente pregunta, estándar de evidencia o recomendación. Las preguntas revelan supuestos, significados, fundamentos, alternativas e implicaciones, conservando la responsabilidad de responder acotadamente. Ayudan a decidir; no sirven para evitar respuestas ni conducir a una conclusión predeterminada.

## Use when

Úsalo si afirmación, términos, alcance, evidencia o consecuencia deseada no están claros y una pequeña aclaración cambia la ruta. Encaja con orientación, enseñanza, deliberación, autoevaluación y definición conjunta de problemas. Solo requiere preguntas para juicios si las respuestas ausentes son realmente decisivas; en otro caso declara un supuesto razonable y continúa.

## Do not use when

No lo uses para tareas mecánicas, respuestas seguras con supuestos acotados ni situaciones donde preguntar repetidamente solo retrasa actuar. No pidas razonamiento privado, datos personales innecesarios ni entrevistas abiertas. Evita preguntas tendenciosas que presuponen la respuesta deseada.

## Inputs to establish

Establece afirmación o decisión, términos por aclarar, alcance, evidencia, alternativas consideradas y consecuencia relevante. Selecciona como máximo tres preguntas decisivas. Indica para cada una qué cambia: marco, evidencia, orden de opciones o finalización. Define una alternativa segura si el usuario no responde.

## Procedure

1. Publica una reformulación neutral de afirmación o decisión y del punto pendiente. Crea un estado de pregunta compartido sin implicar acuerdo.
2. Publica hasta tres preguntas acotadas, cada una con efecto decisorio y formato breve o intervalo permitido. Este conjunto visible es la única petición de aclaración; no añadas un cuestionario oculto.
3. Registra respuestas como proporcionadas por usuario, no respondidas o ambiguas. Publica efectos inmediatos sobre alcance, términos, evidencia o alternativas para visibilizar el cambio de juicio.
4. Publica fundamento de apoyo más fuerte y un contraejemplo o alternativa creíbles surgidos de las respuestas. Distingue respuesta de evidencia sobre el mundo.
5. Publica conclusión provisional o siguiente acción acotada, incluyendo qué puede hacerse sin preguntar otra vez. Si cambia la ruta, dilo claramente sin ocultarlo.
6. Publica incertidumbre restante y condición observable que cambie la conclusión. Usa supuestos para preguntas no respondidas solo si son seguros y reversibles.
7. Publica respuesta actual, por qué se sigue de las entradas respondidas y estado completo, provisional o suspendido. No inventes certeza si la pregunta decisiva sigue sin respuesta.

## Public output contract

Devuelve `no_more_than_three_decisive_questions`, `decisive_questions` (máximo tres), `why_each_matters`, `answers_and_status`, `decision_effects`, `provisional_conclusion`, `remaining_uncertainty`, `next_action` y `flip_condition`. Las preguntas deben ser visibles y acotadas; la tarjeta final no expone transcripciones de deliberación privada. Incluye como máximo dos incertidumbres pendientes. Etiqueta fundamentos **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**.

## Evidence and uncertainty rules

Las respuestas establecen preferencias, alcance o contexto salvo que aporten evidencia comprobable. No las eleves a **verified** sin fuente de apoyo identificable. Una pregunta decisiva no respondida deja la afirmación afectada **assumed**, **unverified** o **held** según importancia. Si las respuestas chocan, muestra el conflicto y no añadas preguntas salvo que una breve pueda resolverlo con seguridad.

## Stop conditions

Detente y formula las preguntas elegidas si continuar sin ellas cambiaría materialmente la acción. No hagas más de tres; si el usuario no responde, usa un supuesto reversible o suspende el juicio. Deja de preguntar cuando ruta y conclusión permitan actuar o solo quede trabajo mecánico.

## Complement handoff

Deriva a `assumption-mapping` solo si aparecen varios supuestos materiales que requieren prioridad y pruebas. Transfiere preguntas respondidas y pendientes, estado de supuestos y condición actual de cambio. El complemento no debe repetir preguntas ni convertirlas en entrevista sin límites.

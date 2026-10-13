## Purpose

Utiliza este procedimiento para conclusiones que normalmente se siguen, pero pueden retirarse ante excepciones o nueva evidencia. Declara una regla por defecto, la aplica provisionalmente, distingue refutadores que contradicen la conclusión de los que debilitan su apoyo y registra condiciones explícitas de retirada. Produce un juicio provisional controlado, no una manera débil de expresar una regla incondicional.

## Use when

Úsalo en derecho, políticas, medicina, operaciones, sentido común y ámbitos donde las generalizaciones admiten excepciones o llega evidencia con el tiempo. Sirve para razonar con «normalmente», «a menos que» y «prima facie», y para juicios que deben seguir revisables sin volverse arbitrarios.

## Do not use when

No lo uses cuando una regla estricta y premisas establecidas implican el resultado, o cuando solo falta clasificar fuentes o actualizar estadísticas. No enumeres todas las excepciones imaginables, trates problemas de credibilidad como contradicciones directas ni prefieras una declaración por ser la más reciente. No afirmes que desconocer refutadores demuestra la conclusión.

## Inputs to establish

Establece regla por defecto, hechos activadores, alcance, excepciones conocidas, posibles refutadores de contradicción y debilitamiento del apoyo, y decisión afectada. Identifica reglas más específicas que puedan prevalecer. Haz como máximo dos preguntas decisivas si regla o hecho activador son poco claros; en otro caso marca la premisa provisional.

## Procedure

1. Publica la regla por defecto acotada, como «normalmente P implica Q», con fuente, alcance y estado probatorio. Así queda visible el estado de la regla.
2. Publica hechos aplicables y conclusión prima facie. Etiquétala provisional e indica las condiciones bajo las que se aplica la regla.
3. Publica por separado refutadores de contradicción que apoyan no-Q y refutadores que debilitan la conexión P-a-Q. Registra cada uno comprobado, alegado o desconocido.
4. Publica reglas rivales y aplica especificidad cuando una sea realmente subconjunto de otra. Si la especificidad no resuelve el conflicto, marca el estado en conflicto o en suspenso, sin usar actualidad ni tono de confianza.
5. Publica condiciones explícitas de retirada: hecho observable que retiraría Q, debilitaría su justificación o exigiría reconsiderarla. La condición debe ser más concreta que «aparece información nueva».
6. Publica estado actualizado tras refutadores conocidos: provisional, respaldado, retirado, en conflicto o en suspenso. Declara si cambió por contradicción, debilitamiento del apoyo o conflicto pendiente.
7. Publica conclusión actual, refutadores aplicables y condición de cambio. Si falta un hecho activador o excepción decisivos, suspende o mantén provisional sin elevar a certeza.

## Public output contract

Devuelve `default_rule`, `applicable_facts`, `prima_facie_conclusion`, `exceptions_defeaters`, `rebutting_defeaters`, `undercutting_defeaters`, `specificity_resolution`, `withdrawal_conditions`, `current_status` y `flip_condition`. La tarjeta debe mostrar provisionalidad y refutadores relevantes. Los fundamentos usan **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**; nunca declares incondicional la conclusión por defecto.

## Evidence and uncertainty rules

Un refutador de contradicción entra en conflicto con la conclusión; uno de debilitamiento reduce la razón por la que los hechos la apoyan sin demostrar lo contrario. La especificidad es prioridad estructural, no regla de actualidad. Comprueba alcance e independencia de evidencia nueva antes de cambiar el estado. Si queda un refutador relevante pendiente, reduce el respaldo o suspende e indica la comprobación necesaria.

## Stop conditions

Detente y haz una pregunta bloqueante si no se identifican regla o hechos activadores y reglas rivales conducen a acciones distintas. Suspende si falta excepción decisiva, fuente o condición de aplicabilidad. Detente cuando la regla sea estricta y sin excepciones o reste actualizar evidencia probabilística.

## Complement handoff

Deriva a `premortem-analysis` cuando la regla provisional apoye un plan elegido y la preocupación restante sea cómo podría fallar. Transfiere conclusión por defecto, refutadores conocidos y condiciones de retirada. El complemento no debe reclasificar refutadores ni repetir el inventario de reglas.

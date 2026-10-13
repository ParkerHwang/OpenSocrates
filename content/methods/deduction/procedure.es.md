## Purpose

Utiliza este procedimiento para determinar si una conclusión se sigue necesariamente de premisas explícitas y una regla, separando validez y verdad de las premisas. Estandariza el argumento, revela premisas ocultas, comprueba la forma e identifica la premisa cuyo fallo invalidaría la conclusión. Una forma válida no vuelve sólido por sí mismo un argumento sobre el mundo real.

## Use when

Úsalo para aplicar reglas, comprobar argumentos formales, interpretar contratos o políticas y afirmaciones según las cuales un resultado debe seguirse de condiciones indicadas. Sirve si pueden explicitarse las premisas pertinentes y se pregunta por implicación lógica, no por generalización empírica.

## Do not use when

No lo uses con premisas inciertas si la tarea real es estimar, diagnosticar, generalizar o actualizar confianza. No trates una premisa probable como demostrada, confundas `P(E|H)` con implicación ni declares válida una forma inválida porque su conclusión casualmente sea verdadera. No inventes una regla que no hayan proporcionado el usuario o fuente rectora.

## Inputs to establish

Establece conclusión propuesta, premisas, regla o implicación rectora, alcance, definiciones y fuente de cada premisa. Marca explícitamente las ocultas e identifica si se requiere validez, solidez o solo resultado condicional. Haz como máximo una pregunta decisiva si una regla o premisa ausentes cambian la forma; en otro caso declara el supuesto condicional.

## Procedure

1. Publica la conclusión y estandariza el argumento en premisas numeradas, regla y conclusión. Marca las premisas ocultas como `[implicit]`; así queda visible la formalización.
2. Publica la forma, como modus ponens, modus tollens, silogismo válido, afirmación del consecuente o negación del antecedente. Si no encaja una forma reconocida, muestra la relación estructural relevante sin forzar etiqueta.
3. Publica el veredicto de validez: suponiendo verdaderas las premisas, ¿debe ser verdadera la conclusión? Declara el patrón de contraejemplo si la forma es inválida.
4. Publica una tabla de estado de premisas con fuente, alcance y estado probatorio de cada premisa y regla. Separa forma válida y argumento sólido; constituye una actualización visible del juicio.
5. Publica la premisa o condición de regla invalidante. Declara exactamente qué rompería la implicación y distingue excepciones a la regla de premisas falsas.
6. Publica la conclusión como sólida, válida pero no sólida, inválida o condicional, con la mínima comprobación ausente. No mejores el estado porque la conclusión parezca plausible.
7. Publica conclusión actual y condición observable de cambio. Si falta una premisa o regla decisiva, suspende la afirmación sobre el mundo real conservando la implicación condicional.

## Public output contract

Devuelve `premises`, `hidden_premises`, `rule`, `rule_or_form`, `conclusion`, `validity_verdict`, `premise_status`, `invalidating_premise`, `soundness_verdict` y `flip_condition`. Debe declarar si la forma es válida y las premisas están respaldadas, sin fusionar ambos aspectos en una sola etiqueta de confianza. Los fundamentos usan **verified**, **computed**, **inferred**, **assumed**, **unverified** o **conflicted**.

## Evidence and uncertainty rules

La validez es una relación estructural y no verifica premisas. Una fuente puede apoyar una premisa sin demostrar que la regla se aplique a este alcance. Las premisas ocultas siguen siendo supuestos hasta respaldarse. Si una premisa se disputa, conserva el resultado condicional y reduce el respaldo o suspende la conclusión aplicada. No uses una única conclusión verdadera para validar una inferencia inválida.

## Stop conditions

Detente y haz una pregunta bloqueante si falta la regla rectora o conclusión y las formas posibles llevan a resultados distintos. Suspende cuando no pueda comprobarse una premisa relevante, comunicando el condicional válido si existe. Detente si la tarea es probabilística, causal o comparativa, en vez de implicación.

## Complement handoff

Deriva a `conceptual-analysis` cuando la disputa formal dependa de un término ambiguo o definición de alcance. Transfiere premisas estandarizadas, término disputado y regla afectada. El complemento debe aclarar el concepto sin rehacer el veredicto de validez.
